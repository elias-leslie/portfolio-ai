"""Cross-vendor price check orchestrator (phase 3).

One run prices a capped product list (watched first, then most-purchased)
against Amazon/Walmart/Publix via the ``household-price-scout`` Agent Hub
agent — one agentic web call per vendor, each isolated so a blocked or
failing vendor never sinks the others. Quotes persist as
``source='vendor_quote'`` price observations (so they ride the existing
sparklines), and the findings service turns them into in-app savings
findings. Every agent call is audited in ``agent_runs``.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdPriceCheckRun,
    HouseholdPriceCheckStatus,
    HouseholdPriceCheckVendorStatus,
)
from app.repositories.agent_repository import AgentRunRepository
from app.services._household_finance_utils import iso_or_none, to_float
from app.services._household_report_builder import _extract_package_measure
from app.services._price_firecrawl_lookup import (
    lookup_vendor_prices_with_firecrawl,
    vendor_result_to_json,
)
from app.services._price_vendor_adapters import (
    VENDOR_ADAPTERS,
    VendorAdapter,
    VendorQuote,
    VendorResult,
)
from app.services.household_price_findings_service import (
    FindingCandidate,
    HouseholdPriceFindingsService,
)
from app.services.household_purchase_item_service import HouseholdPurchaseItemService
from app.storage import get_storage

logger = get_logger(__name__)

PRICE_SCOUT_AGENT_SLUG = "household-price-scout"
PRODUCT_CAP_PER_RUN = 12
# A queued/running row older than this is a dead run (worker crash), not a
# reason to refuse a new trigger.
RUN_ACTIVE_WINDOW_MINUTES = 30
MIN_VENDOR_QUOTE_CONFIDENCE = 0.7

_UNIT_LABELS = {
    "weight_oz": "oz",
    "volume_fl_oz": "fl oz",
    "count": "ct",
}


class HouseholdPriceCheckService:
    def __init__(self) -> None:
        self.storage = get_storage()
        self.findings_service = HouseholdPriceFindingsService()
        # Test seam: swapped for a stub in unit tests.
        from app.agents.clients.agent_hub_client import AgentHubAPIClient  # noqa: PLC0415

        self._client_cls = AgentHubAPIClient

    # -- trigger/status ------------------------------------------------------

    def start_run(
        self,
        *,
        triggered_by: str,
        product_limit: int | None = None,
        product_ids: list[str] | None = None,
        shopping_list_id: str | None = None,
    ) -> tuple[str, bool]:
        """Create a queued run; returns (run_id, already_running)."""
        limit = max(1, min(int(product_limit or PRODUCT_CAP_PER_RUN), PRODUCT_CAP_PER_RUN))
        metadata = {
            "product_limit": limit,
            "product_ids": product_ids or [],
            "shopping_list_id": shopping_list_id,
            "triggered_by": triggered_by,
        }
        with self.storage.connection() as conn:
            active = conn.execute(
                """
                SELECT id FROM household_price_check_runs
                WHERE status IN ('queued', 'running')
                  AND created_at > CURRENT_TIMESTAMP - make_interval(mins => %s)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [RUN_ACTIVE_WINDOW_MINUTES],
            ).fetchone()
            if active is not None:
                return str(active[0]), True
            run_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO household_price_check_runs (
                    id, status, triggered_by, metadata
                ) VALUES (%s, 'queued', %s, %s::jsonb)
                """,
                [run_id, triggered_by, json.dumps(metadata)],
            )
            conn.commit()
        return run_id, False

    def mark_run_failed(self, run_id: str, error: str) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_price_check_runs
                SET status = 'failed', error = %s,
                    finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [error[:2000], run_id],
            )
            conn.commit()

    def get_status(self) -> HouseholdPriceCheckStatus:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id, status, triggered_by, product_count, quote_count,
                       finding_count, error, started_at, finished_at, vendor_status
                FROM household_price_check_runs
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
        return HouseholdPriceCheckStatus(
            generated_at=datetime.now(UTC).isoformat(),
            latest_run=_run_model(row) if row is not None else None,
            open_findings=self.findings_service.list_open_findings(),
        )

    # -- execution -----------------------------------------------------------

    def execute_run(self, run_id: str) -> dict[str, Any]:
        with self.storage.connection() as conn:
            row = conn.execute(
                "SELECT metadata FROM household_price_check_runs WHERE id = %s",
                [run_id],
            ).fetchone()
            if row is None:
                return {"status": "error", "error": f"Run not found: {run_id}"}
            metadata = row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
            conn.execute(
                """
                UPDATE household_price_check_runs
                SET status = 'running', started_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [run_id],
            )
            conn.commit()

        try:
            return self._execute(run_id, metadata)
        except Exception as exc:
            logger.warning("price_check_run_failed", run_id=run_id, error=str(exc))
            self._finish_agent_workflow(run_id, status="failed", result={"error": str(exc)})
            self.mark_run_failed(run_id, str(exc))
            return {"status": "failed", "error": str(exc)}

    def _execute(self, run_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        limit = max(
            1, min(int(metadata.get("product_limit") or PRODUCT_CAP_PER_RUN), PRODUCT_CAP_PER_RUN)
        )
        with self.storage.connection() as conn:
            products = self._select_products(
                conn,
                limit=limit,
                product_ids=list(metadata.get("product_ids") or []),
                shopping_list_id=metadata.get("shopping_list_id"),
            )
            vendors = self._enabled_vendors(conn)
            self._ensure_agent_workflow(conn, run_id, metadata=metadata)
            conn.commit()  # vendor profile seeding

        results = _run_vendor_checks(
            vendors,
            lambda adapter: self._check_vendor(adapter, products, price_check_run_id=run_id),
        )

        quote_count = 0
        with self.storage.connection() as conn:
            for adapter in vendors:
                result = results[adapter.vendor_key]
                merchant_id = self._vendor_merchant_id(conn, adapter)
                for quote in result.quotes:
                    if quote.product_id not in {p["id"] for p in products}:
                        continue
                    self._upsert_quote_observation(
                        conn,
                        quote=quote,
                        merchant_id=merchant_id,
                        vendor_key=adapter.vendor_key,
                        run_id=run_id,
                    )
                    quote_count += 1
            finding_count = self.findings_service.replace_run_findings(
                conn,
                run_id=run_id,
                candidates=_finding_candidates(products, vendors, results),
            )
            run_status = _completion_status(results)
            vendor_status = {
                key: {
                    "status": result.status,
                    "quote_count": len(result.quotes),
                    "error": result.error,
                }
                for key, result in results.items()
            }
            conn.execute(
                """
                UPDATE household_price_check_runs
                SET status = %s, product_count = %s, quote_count = %s,
                    finding_count = %s, vendor_status = %s::jsonb,
                    finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [
                    run_status,
                    len(products),
                    quote_count,
                    finding_count,
                    json.dumps(vendor_status),
                    run_id,
                ],
            )
            conn.execute(
                """
                UPDATE agent_workflows
                SET status = 'complete',
                    current_step = %s,
                    result = %s::jsonb,
                    completed_at = CURRENT_TIMESTAMP,
                    last_updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [
                    run_status,
                    json.dumps(
                        {
                            "status": run_status,
                            "product_count": len(products),
                            "quote_count": quote_count,
                            "finding_count": finding_count,
                            "vendor_status": vendor_status,
                        }
                    ),
                    run_id,
                ],
            )
            conn.commit()

        logger.info(
            "price_check_run_completed",
            run_id=run_id,
            status=run_status,
            products=len(products),
            quotes=quote_count,
            findings=finding_count,
        )
        return {
            "status": run_status,
            "run_id": run_id,
            "products": len(products),
            "quotes": quote_count,
            "findings": finding_count,
        }

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _ensure_agent_workflow(
        conn: Any,
        run_id: str,
        *,
        metadata: dict[str, Any],
    ) -> None:
        """Agent-run audit rows FK to agent_workflows, so create the parent row."""
        conn.execute(
            """
            INSERT INTO agent_workflows (
                id, workflow_type, status, current_step, agents_involved,
                shared_context, started_at, triggered_by, priority,
                max_duration_seconds
            ) VALUES (
                %s, 'household_price_check', 'running', 'checking vendor prices',
                %s::text[], %s::jsonb, CURRENT_TIMESTAMP, %s, 5, 3600
            )
            ON CONFLICT (id) DO NOTHING
            """,
            [
                run_id,
                [PRICE_SCOUT_AGENT_SLUG],
                json.dumps({"metadata": metadata, "run_id": run_id}),
                metadata.get("triggered_by") or "manual",
            ],
        )

    def _finish_agent_workflow(
        self,
        run_id: str,
        *,
        status: str,
        result: dict[str, Any],
    ) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_workflows
                SET status = %s,
                    current_step = %s,
                    result = %s::jsonb,
                    completed_at = CURRENT_TIMESTAMP,
                    last_updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [status, status, json.dumps(result), run_id],
            )
            conn.commit()

    @staticmethod
    def _select_products(
        conn: Any,
        *,
        limit: int,
        product_ids: list[str] | None = None,
        shopping_list_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Explicit/list products first, then watched and repeat 90-day buys."""
        rows = conn.execute(
            """
            WITH explicit_products AS (
                SELECT unnest(%s::uuid[]) AS product_id
            ),
            list_products AS (
                SELECT DISTINCT product_id
                FROM household_shopping_list_items
                WHERE status = 'open'
                  AND product_id IS NOT NULL
                  AND (%s::uuid IS NULL OR shopping_list_id = %s::uuid)
            ),
            items AS (
                SELECT product_id, COUNT(*) AS purchase_count
                FROM household_purchase_items
                WHERE removed IS NOT TRUE AND product_id IS NOT NULL
                  AND purchase_date >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY product_id
            ),
            eligible_products AS (
                SELECT product_id FROM explicit_products
                UNION
                SELECT product_id FROM list_products
                UNION
                SELECT product_id FROM items WHERE purchase_count >= 2
                UNION
                SELECT id AS product_id FROM household_products WHERE watched IS TRUE
            ),
            last_paid AS (
                SELECT DISTINCT ON (product_id)
                       product_id,
                       total_price / NULLIF(package_normalized_quantity, 0)
                           AS comparison_unit_price,
                       package_display_label,
                       package_normalized_quantity,
                       package_normalized_unit,
                       observed_date
                FROM household_product_price_observations
                WHERE source <> 'vendor_quote'
                  AND package_normalized_quantity IS NOT NULL
                  AND package_normalized_quantity > 0
                  AND package_normalized_unit IS NOT NULL
                ORDER BY product_id, observed_date DESC, created_at DESC
            )
            SELECT p.id::text, p.canonical_name, p.brand, p.package_display_label,
                   COALESCE(i.purchase_count, 0), lp.comparison_unit_price,
                   lp.package_display_label AS baseline_package_label,
                   lp.package_normalized_quantity AS baseline_package_quantity,
                   lp.package_normalized_unit AS baseline_package_unit
            FROM eligible_products ep
            JOIN household_products p ON p.id = ep.product_id
            LEFT JOIN items i ON i.product_id = p.id
            LEFT JOIN last_paid lp ON lp.product_id = p.id
            LEFT JOIN explicit_products e ON e.product_id = p.id
            LEFT JOIN list_products l ON l.product_id = p.id
            ORDER BY (e.product_id IS NOT NULL) DESC,
                     (l.product_id IS NOT NULL) DESC,
                     p.watched DESC, i.purchase_count DESC NULLS LAST,
                     lp.observed_date DESC NULLS LAST, p.id
            LIMIT %s
            """,
            [product_ids or [], shopping_list_id, shopping_list_id, limit],
        ).fetchall()
        return [
            {
                "id": str(row[0]),
                "name": str(row[1] or ""),
                "brand": str(row[2]) if row[2] else None,
                "package": str(row[3]) if row[3] else None,
                "purchase_count": int(row[4] or 0),
                "last_paid": to_float(row[5]),
                "baseline_package_label": str(row[6]) if row[6] else None,
                "baseline_package_quantity": to_float(row[7]),
                "baseline_package_unit": str(row[8]) if row[8] else None,
            }
            for row in rows
        ]

    @staticmethod
    def _enabled_vendors(conn: Any) -> list[VendorAdapter]:
        """Seed vendor profiles on first run; respect the enabled flag after."""
        for adapter in VENDOR_ADAPTERS:
            conn.execute(
                """
                INSERT INTO household_vendor_profiles (id, vendor_key, display_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (vendor_key) DO NOTHING
                """,
                [str(uuid.uuid4()), adapter.vendor_key, adapter.display_name],
            )
        disabled = {
            str(row[0])
            for row in conn.execute(
                "SELECT vendor_key FROM household_vendor_profiles WHERE enabled IS NOT TRUE"
            ).fetchall()
        }
        return [a for a in VENDOR_ADAPTERS if a.vendor_key not in disabled]

    def _check_vendor(
        self,
        adapter: VendorAdapter,
        products: list[dict[str, Any]],
        *,
        price_check_run_id: str,
    ) -> VendorResult:
        """One audited agent call: search this vendor for every product."""
        from agent_hub.models.content import MessageInput, TextContent  # noqa: PLC0415

        prompt = adapter.build_prompt(products)
        client = self._client_cls(agent_slug=PRICE_SCOUT_AGENT_SLUG, use_memory=False)
        agent_run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        repo = AgentRunRepository(self.storage)
        repo.create_run(
            run_id=agent_run_id,
            agent_type=PRICE_SCOUT_AGENT_SLUG,
            model=client.get_model_name(),
            started_at=started_at,
            provider=client.provider,
            run_type="automated",
            workflow_id=price_check_run_id,
        )
        repo.store_message(agent_run_id, "user", prompt)
        try:
            response = client.complete_messages(
                messages=[
                    MessageInput(role="user", content=[TextContent(text=prompt)])
                ],
                execute_tools=True,
                max_turns=10,
                purpose=f"household_price_check:{adapter.vendor_key}",
            )
        except Exception as exc:
            repo.complete_run(
                run_id=agent_run_id,
                completed_at=datetime.now(UTC),
                status="error",
                num_ideas=0,
                error_message=str(exc)[:2000],
            )
            raise
        finally:
            client.close()
        repo.store_message(agent_run_id, "assistant", response.content)
        result = adapter.parse_response(response.content)
        if not result.quotes and result.status in {"blocked", "error"}:
            fallback = lookup_vendor_prices_with_firecrawl(adapter, products)
            if fallback.quotes:
                repo.store_message(
                    agent_run_id,
                    "assistant",
                    f"Firecrawl fallback: {vendor_result_to_json(fallback)}",
                )
                result = fallback
        repo.complete_run(
            run_id=agent_run_id,
            completed_at=datetime.now(UTC),
            status="completed" if result.status == "ok" else result.status,
            num_ideas=len(result.quotes),
            error_message=result.error,
        )
        return result

    @staticmethod
    def _vendor_merchant_id(conn: Any, adapter: VendorAdapter) -> str | None:
        return HouseholdPurchaseItemService._lookup_or_create_merchant(
            conn,
            raw_merchant=adapter.merchant_name,
            category="Retail",
            essentiality="mixed",
        )

    @staticmethod
    def _upsert_quote_observation(
        conn: Any,
        *,
        quote: VendorQuote,
        merchant_id: str | None,
        vendor_key: str,
        run_id: str,
    ) -> None:
        """Persist one quote variant per product+vendor+day.

        The buy guide needs both nearest-size and larger-size quotes. Re-runs
        update the same quote_key instead of collapsing every vendor result into
        one row.
        """
        quote_key = _quote_key(quote)
        measure = _quote_package_measure(quote)
        metadata = json.dumps(
            {
                "vendor_key": vendor_key,
                "run_id": run_id,
                "quote_key": quote_key,
                "title": quote.title,
                "url": quote.url,
                "promo_text": quote.promo_text,
                "membership_required": quote.membership_required,
                "availability": quote.availability,
                "confidence": quote.confidence,
                "quote_kind": quote.quote_kind,
            }
        )
        existing = conn.execute(
            """
            SELECT id FROM household_product_price_observations
            WHERE product_id = %s AND source = 'vendor_quote'
              AND observed_date = CURRENT_DATE
              AND merchant_id IS NOT DISTINCT FROM %s
              AND metadata->>'quote_key' = %s
            LIMIT 1
            """,
            [quote.product_id, merchant_id, quote_key],
        ).fetchone()
        if existing is not None:
            conn.execute(
                """
                UPDATE household_product_price_observations
                SET total_price = %s, unit_price = %s, package_display_label = %s,
                    package_normalized_quantity = %s,
                    package_normalized_unit = %s,
                    metadata = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [
                    quote.price,
                    quote.unit_price,
                    quote.package_label,
                    measure.normalized_quantity if measure is not None else None,
                    measure.normalized_unit if measure is not None else None,
                    metadata,
                    existing[0],
                ],
            )
            return
        conn.execute(
            """
            INSERT INTO household_product_price_observations (
                id, product_id, merchant_id, observed_date, total_price,
                unit_price, package_display_label, package_normalized_quantity,
                package_normalized_unit, source, metadata
            ) VALUES (
                %s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, 'vendor_quote', %s::jsonb
            )
            """,
            [
                str(uuid.uuid4()),
                quote.product_id,
                merchant_id,
                quote.price,
                quote.unit_price,
                quote.package_label,
                measure.normalized_quantity if measure is not None else None,
                measure.normalized_unit if measure is not None else None,
                metadata,
            ],
        )


def _quote_key(quote: VendorQuote) -> str:
    """Stable-enough same-day quote identity for nearest/bulk variants."""
    raw = "|".join(
        part.strip().lower()
        for part in (
            quote.url or "",
            quote.title,
            quote.package_label or "",
            quote.quote_kind,
        )
        if part
    )
    key = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return key[:160] or str(uuid.uuid5(uuid.NAMESPACE_URL, quote.title))


def _quote_package_measure(quote: VendorQuote) -> Any:
    text = " ".join(part for part in (quote.package_label, quote.title) if part)
    if not text.strip():
        return None
    return _extract_package_measure(text, {"Product Name": text})


def _run_vendor_checks(
    vendors: list[VendorAdapter],
    check: Any,
) -> dict[str, VendorResult]:
    """Vendor isolation: one blocked/broken vendor must not sink the run."""
    results: dict[str, VendorResult] = {}
    for adapter in vendors:
        try:
            results[adapter.vendor_key] = check(adapter)
        except Exception as exc:
            logger.warning(
                "price_check_vendor_failed", vendor=adapter.vendor_key, error=str(exc)
            )
            results[adapter.vendor_key] = VendorResult(
                vendor_key=adapter.vendor_key, status="error", error=str(exc)[:500]
            )
    return results


def _completion_status(results: dict[str, VendorResult]) -> str:
    """A usable run with any blocked/error/partial vendor is visibly degraded."""
    if any(result.status in {"blocked", "error", "partial"} for result in results.values()):
        return "completed_with_errors"
    return "completed"


def _finding_candidates(
    products: list[dict[str, Any]],
    vendors: list[VendorAdapter],
    results: dict[str, VendorResult],
) -> list[FindingCandidate]:
    """Best compatible unit-cost quote per product vs what the household last paid."""
    products_by_id = {str(product["id"]): product for product in products}
    by_product: dict[str, tuple[str, VendorQuote, float]] = {}
    for adapter in vendors:
        for quote in results[adapter.vendor_key].quotes:
            product = products_by_id.get(quote.product_id)
            if product is None:
                continue
            unit_cost = _quote_unit_cost_for_product(quote, product)
            if unit_cost is None:
                continue
            current = by_product.get(quote.product_id)
            if current is None or unit_cost < current[2]:
                by_product[quote.product_id] = (adapter.vendor_key, quote, unit_cost)
    candidates: list[FindingCandidate] = []
    for product in products:
        best = by_product.get(product["id"])
        if best is None or product.get("last_paid") is None:
            continue
        vendor_key, quote, vendor_unit_cost = best
        household_unit_cost = float(product["last_paid"])
        if vendor_unit_cost >= household_unit_cost:
            continue
        unit_label = _unit_label(str(product.get("baseline_package_unit") or ""))
        baseline_quantity = to_float(product.get("baseline_package_quantity")) or 1.0
        candidates.append(
            FindingCandidate(
                product_id=product["id"],
                product_name=product["name"],
                purchase_count=int(product.get("purchase_count") or 0),
                household_price=household_unit_cost,
                vendor_key=vendor_key,
                vendor_price=vendor_unit_cost,
                unit_label=unit_label,
                comparison_quantity=baseline_quantity,
                household_package_label=product.get("baseline_package_label"),
                household_equivalent_total=round(household_unit_cost * baseline_quantity, 2),
                vendor_total_price=quote.price,
                vendor_equivalent_total=round(vendor_unit_cost * baseline_quantity, 2),
                vendor_url=quote.url,
                vendor_title=quote.title,
                vendor_package_label=quote.package_label,
                vendor_promo_text=quote.promo_text,
            )
        )
    return candidates


def _quote_unit_cost_for_product(quote: VendorQuote, product: dict[str, Any]) -> float | None:
    """Return quote cost on the product's normalized unit basis, or None if unsafe."""
    baseline_unit = str(product.get("baseline_package_unit") or "").strip()
    if not baseline_unit:
        return None
    if (quote.confidence or 0.0) < MIN_VENDOR_QUOTE_CONFIDENCE:
        return None
    measure = _quote_package_measure(quote)
    if measure is None or measure.normalized_unit != baseline_unit:
        return None
    if quote.price <= 0 or measure.normalized_quantity <= 0:
        return None
    return round(float(quote.price) / float(measure.normalized_quantity), 4)


def _unit_label(unit: str) -> str:
    return _UNIT_LABELS.get(unit, unit.replace("_", " "))


def _run_model(row: Any) -> HouseholdPriceCheckRun:
    vendor_status = row[9] if isinstance(row[9], dict) else json.loads(row[9] or "{}")
    return HouseholdPriceCheckRun(
        id=str(row[0]),
        status=str(row[1]),
        triggered_by=str(row[2] or "manual"),
        product_count=int(row[3] or 0),
        quote_count=int(row[4] or 0),
        finding_count=int(row[5] or 0),
        error=str(row[6]) if row[6] else None,
        started_at=iso_or_none(row[7]),
        finished_at=iso_or_none(row[8]),
        vendors=[
            HouseholdPriceCheckVendorStatus(
                vendor_key=str(key),
                status=str(value.get("status") or "error"),
                quote_count=int(value.get("quote_count") or 0),
                error=value.get("error"),
            )
            for key, value in sorted(vendor_status.items())
        ],
    )
