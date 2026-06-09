"""Facade over the credit-card layer.

Loads products and owned cards from the DB, derives the spend profile from real
household transactions, and hands them to the deterministic rewards / rotation
engines (plan §6). Also owns CRUD for the user's cards and persistence of chosen
rotation plans. Mirrors the household.py service pattern: one ``@lru_cache``
singleton, called via ``run_in_threadpool`` from the router.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.logging_config import get_logger
from app.models.credit_cards import (
    CardRanking,
    CreditCardCreate,
    CreditCardProduct,
    CreditCardUpdate,
    HouseholdCreditCard,
    RankingRequest,
    RotationPlanView,
    RotationRequest,
    SpendProfile,
)
from app.services.card_rewards_service import (
    DEFAULT_BUCKET_MIX,
    DEFAULT_MONTHLY_TOTAL,
    CardRewardsService,
)
from app.services.card_rotation_engine import CardRotationEngine
from app.services.household_transaction_service import HouseholdTransactionService
from app.storage import get_storage

logger = get_logger(__name__)

_PRODUCT_COLUMNS = (
    "id, slug, issuer, network, product_name, card_kind, annual_fee, reward_multipliers, "
    "point_program, est_point_value_cents, welcome_bonus_points, welcome_bonus_cash, "
    "welcome_min_spend, welcome_window_days, transfer_partners, credits, issuer_rules, "
    "source, source_document_id, last_verified_at, created_at, updated_at"
)

_CARD_COLUMNS = (
    "id, product_id, household_account_id, status, is_primary_active, opened_date, "
    "closed_date, annual_fee_due_date, welcome_progress_amount, welcome_deadline, "
    "welcome_status, notes, metadata, created_at, updated_at"
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _json(value: object) -> str:
    return json.dumps(value, default=str)


def _loads(value: object, default: object) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value or "null") if value else default
    return value


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _row_to_product(row: tuple[Any, ...]) -> CreditCardProduct:
    return CreditCardProduct(
        id=str(row[0]),
        slug=str(row[1]),
        issuer=str(row[2]),
        network=str(row[3]) if row[3] else None,
        product_name=str(row[4]),
        card_kind=str(row[5]),
        annual_fee=float(row[6]),
        reward_multipliers={k: float(v) for k, v in (_loads(row[7], {}) or {}).items()},
        point_program=str(row[8]) if row[8] else None,
        est_point_value_cents=float(row[9]) if row[9] is not None else None,
        welcome_bonus_points=int(row[10] or 0),
        welcome_bonus_cash=float(row[11] or 0.0),
        welcome_min_spend=float(row[12]) if row[12] is not None else None,
        welcome_window_days=int(row[13]) if row[13] is not None else None,
        transfer_partners=list(_loads(row[14], []) or []),
        credits=list(_loads(row[15], []) or []),
        issuer_rules=dict(_loads(row[16], {}) or {}),
        source=str(row[17]),
        source_document_id=str(row[18]) if row[18] else None,
        last_verified_at=_iso(row[19]),
        created_at=_iso(row[20]),
        updated_at=_iso(row[21]),
    )


def _row_to_card(row: tuple[Any, ...]) -> HouseholdCreditCard:
    return HouseholdCreditCard(
        id=str(row[0]),
        product_id=str(row[1]),
        household_account_id=str(row[2]) if row[2] else None,
        status=str(row[3]),
        is_primary_active=bool(row[4]),
        opened_date=_iso(row[5]),
        closed_date=_iso(row[6]),
        annual_fee_due_date=_iso(row[7]),
        welcome_progress_amount=float(row[8] or 0.0),
        welcome_deadline=_iso(row[9]),
        welcome_status=str(row[10]),
        notes=str(row[11]) if row[11] else None,
        metadata=dict(_loads(row[12], {}) or {}),
        created_at=_iso(row[13]),
        updated_at=_iso(row[14]),
    )


class CardManagementService:
    def __init__(self, storage: Any | None = None) -> None:
        self.storage = storage or get_storage()
        self._rewards = CardRewardsService()
        self._rotation = CardRotationEngine(self._rewards)
        self._txn_service: Any | None = None

    @property
    def transaction_service(self) -> Any:
        if self._txn_service is None:
            self._txn_service = HouseholdTransactionService()
        return self._txn_service

    # ------------------------------------------------------------------ catalog

    def _load_products(self, *, owned_only: bool = False) -> list[CreditCardProduct]:
        with self.storage.connection() as conn:
            if owned_only:
                rows = conn.execute(
                    f"""
                    SELECT {_PRODUCT_COLUMNS}
                    FROM credit_card_products
                    WHERE id IN (SELECT DISTINCT product_id FROM household_credit_cards)
                    ORDER BY issuer, product_name
                    """,
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT {_PRODUCT_COLUMNS} FROM credit_card_products ORDER BY issuer, product_name",
                ).fetchall()
        return [_row_to_product(row) for row in rows]

    def get_catalog(self) -> list[CreditCardProduct]:
        return self._load_products()

    # ------------------------------------------------------------- owned cards

    def list_owned_cards(self) -> list[HouseholdCreditCard]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                f"SELECT {_CARD_COLUMNS} FROM household_credit_cards ORDER BY is_primary_active DESC, created_at DESC",
            ).fetchall()
        cards = [_row_to_card(row) for row in rows]
        products = {p.id: p for p in self._load_products()}
        for card in cards:
            card.product = products.get(card.product_id)
        return cards

    def _get_card(self, conn: Any, card_id: str) -> HouseholdCreditCard:
        row = conn.execute(
            f"SELECT {_CARD_COLUMNS} FROM household_credit_cards WHERE id = %s",
            [card_id],
        ).fetchone()
        if row is None:
            raise KeyError(f"Credit card {card_id} not found.")
        return _row_to_card(row)

    def create_owned_card(self, req: CreditCardCreate) -> HouseholdCreditCard:
        card_id = str(uuid.uuid4())
        now = _now()
        with self.storage.connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM credit_card_products WHERE id = %s", [req.product_id]
            ).fetchone()
            if exists is None:
                raise KeyError(f"Product {req.product_id} not found.")
            conn.execute(
                """
                INSERT INTO household_credit_cards (
                    id, product_id, household_account_id, status, opened_date,
                    welcome_deadline, notes, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    card_id,
                    req.product_id,
                    req.household_account_id,
                    req.status,
                    _opt_date(req.opened_date),
                    _opt_date(req.welcome_deadline),
                    req.notes,
                    now,
                    now,
                ],
            )
            conn.commit()
            card = self._get_card(conn, card_id)
        logger.info("credit_card_created", card_id=card_id, product_id=req.product_id)
        return card

    def update_owned_card(self, card_id: str, req: CreditCardUpdate) -> HouseholdCreditCard:
        fields = req.model_dump(exclude_none=True)
        if not fields:
            with self.storage.connection() as conn:
                return self._get_card(conn, card_id)
        date_fields = {"opened_date", "closed_date", "annual_fee_due_date", "welcome_deadline"}
        sets: list[str] = []
        params: list[Any] = []
        for key, value in fields.items():
            sets.append(f"{key} = %s")
            params.append(_opt_date(value) if key in date_fields else value)
        params.append(_now())
        params.append(card_id)
        with self.storage.connection() as conn:
            result = conn.execute(
                f"UPDATE household_credit_cards SET {', '.join(sets)}, updated_at = %s WHERE id = %s",
                params,
            )
            if not (getattr(result, "rowcount", 0) or 0):
                raise KeyError(f"Credit card {card_id} not found.")
            conn.commit()
            return self._get_card(conn, card_id)

    def activate_card(self, card_id: str) -> HouseholdCreditCard:
        """Flip the "one card at a time" pointer to this card (plan §7)."""
        now = _now()
        with self.storage.connection() as conn:
            target = self._get_card(conn, card_id)
            # Clear the current primary before setting the new one (the partial
            # unique index allows at most one is_primary_active=TRUE).
            conn.execute(
                """
                UPDATE household_credit_cards
                SET is_primary_active = FALSE,
                    status = CASE WHEN status = 'active' THEN 'rotated_out' ELSE status END,
                    updated_at = %s
                WHERE is_primary_active = TRUE AND id <> %s
                """,
                [now, card_id],
            )
            conn.execute(
                """
                UPDATE household_credit_cards
                SET is_primary_active = TRUE, status = 'active', updated_at = %s
                WHERE id = %s
                """,
                [now, card_id],
            )
            conn.commit()
            card = self._get_card(conn, card_id)
        logger.info("credit_card_activated", card_id=card_id, product_id=target.product_id)
        return card

    def delete_owned_card(self, card_id: str) -> None:
        with self.storage.connection() as conn:
            result = conn.execute(
                "DELETE FROM household_credit_cards WHERE id = %s", [card_id]
            )
            if not (getattr(result, "rowcount", 0) or 0):
                raise KeyError(f"Credit card {card_id} not found.")
            conn.commit()
        logger.info("credit_card_deleted", card_id=card_id)

    # --------------------------------------------------------- spend profile

    def _resolve_profile(
        self, *, monthly_total: float | None, by_bucket: dict[str, float] | None
    ) -> SpendProfile:
        try:
            view = self.transaction_service.build_spending_view(window="3m")
            profile = self._rewards.build_spend_profile(view)
        except Exception:
            logger.warning("card_spend_profile_fallback", exc_info=True)
            profile = SpendProfile(
                monthly_total=DEFAULT_MONTHLY_TOTAL,
                by_bucket=dict(DEFAULT_BUCKET_MIX),
                source="default",
            )
        return self._rewards.apply_overrides(profile, monthly_total=monthly_total, by_bucket=by_bucket)

    # ---------------------------------------------------------------- ranking

    def build_ranking(self, req: RankingRequest) -> CardRanking:
        products = self._load_products(owned_only=req.include_owned_only)
        profile = self._resolve_profile(monthly_total=req.monthly_total, by_bucket=req.by_bucket)
        return self._rewards.rank(
            products,
            profile,
            stance=req.valuation_stance,
            overrides=req.point_value_overrides,
            amortization_years=req.amortization_years,
        )

    # --------------------------------------------------------------- rotation

    def build_rotation(self, req: RotationRequest) -> RotationPlanView:
        products = self._load_products()
        profile = self._resolve_profile(monthly_total=req.monthly_total, by_bucket=req.by_bucket)
        view = self._rotation.build_rotation_plan(
            products,
            profile,
            objective=req.objective,
            horizon_quarters=req.horizon_quarters,
            stance=req.valuation_stance,
            overrides=req.point_value_overrides,
            name=req.name,
        )
        if req.persist:
            view.plan_id = self._persist_rotation_plan(view, profile)
        return view

    def _persist_rotation_plan(self, view: RotationPlanView, profile: SpendProfile) -> str:
        plan_id = str(uuid.uuid4())
        now = _now()
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO card_rotation_plans (
                    id, name, objective, horizon_quarters, assumed_monthly_spend,
                    spend_profile, projected_total_value, baseline_single_card_value,
                    status, generated_at, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, 'active', %s, %s, %s)
                """,
                [
                    plan_id,
                    view.name,
                    view.objective,
                    view.horizon_quarters,
                    _money(profile.monthly_total),
                    _json(profile.model_dump()),
                    _money(view.projected_total_value),
                    _money(view.baseline_single_card_value),
                    now,
                    now,
                    now,
                ],
            )
            for step in view.steps:
                conn.execute(
                    """
                    INSERT INTO card_rotation_steps (
                        id, plan_id, sequence_index, product_id, household_credit_card_id,
                        action, target_spend, projected_welcome_value, projected_earn_value,
                        rule_warnings, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    """,
                    [
                        str(uuid.uuid4()),
                        plan_id,
                        step.sequence_index,
                        step.product_id,
                        step.household_credit_card_id,
                        step.action,
                        _money(step.target_spend),
                        _money(step.projected_welcome_value),
                        _money(step.projected_earn_value),
                        _json(step.rule_warnings),
                        now,
                        now,
                    ],
                )
            conn.commit()
        logger.info("rotation_plan_persisted", plan_id=plan_id, steps=len(view.steps))
        return plan_id

    def list_rotation_plans(self) -> list[dict[str, Any]]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, objective, horizon_quarters, assumed_monthly_spend,
                       projected_total_value, baseline_single_card_value, status, generated_at
                FROM card_rotation_plans
                ORDER BY generated_at DESC
                """,
            ).fetchall()
        return [
            {
                "plan_id": str(row[0]),
                "name": str(row[1]),
                "objective": str(row[2]),
                "horizon_quarters": int(row[3]),
                "assumed_monthly_spend": float(row[4]),
                "projected_total_value": float(row[5]) if row[5] is not None else None,
                "baseline_single_card_value": float(row[6]) if row[6] is not None else None,
                "status": str(row[7]),
                "generated_at": _iso(row[8]),
            }
            for row in rows
        ]

    def get_rotation_plan(self, plan_id: str) -> RotationPlanView:
        """Rebuild the view from the persisted profile so charts stay consistent."""
        with self.storage.connection() as conn:
            plan = conn.execute(
                """
                SELECT name, objective, horizon_quarters, spend_profile
                FROM card_rotation_plans WHERE id = %s
                """,
                [plan_id],
            ).fetchone()
        if plan is None:
            raise KeyError(f"Rotation plan {plan_id} not found.")
        stored_profile = _loads(plan[3], {}) or {}
        req = RotationRequest(
            objective=str(plan[1]),
            horizon_quarters=int(plan[2]),
            monthly_total=float(stored_profile.get("monthly_total") or 0) or None,
            by_bucket={k: float(v) for k, v in (stored_profile.get("by_bucket") or {}).items()} or None,
            name=str(plan[0]),
        )
        view = self.build_rotation(req)
        view.plan_id = plan_id
        return view


def _opt_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])
