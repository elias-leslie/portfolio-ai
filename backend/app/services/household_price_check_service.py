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


class HouseholdPriceCheckService:
    def __init__(self) -> None:
        self.storage = get_storage()
        self.findings_service = HouseholdPriceFindingsService()
        # Test seam: swapped for a stub in unit tests.
        from app.agents.clients.agent_hub_client import AgentHubAPIClient  # noqa: PLC0415

        self._client_cls = AgentHubAPIClient

    # -- trigger/status ------------------------------------------------------

    def start_run(
        self, *, triggered_by: str, product_limit: int | None = None
    ) -> tuple[str, bool]:
        """Create a queued run; returns (run_id, already_running)."""
        limit = max(1, min(int(product_limit or PRODUCT_CAP_PER_RUN), PRODUCT_CAP_PER_RUN))
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
                [run_id, triggered_by, json.dumps({"product_limit": limit})],
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
            self.mark_run_failed(run_id, str(exc))
            return {"status": "failed", "error": str(exc)}

    def _execute(self, run_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        limit = max(
            1, min(int(metadata.get("product_limit") or PRODUCT_CAP_PER_RUN), PRODUCT_CAP_PER_RUN)
        )
        with self.storage.connection() as conn:
            products = self._select_products(conn, limit=limit)
            vendors = self._enabled_vendors(conn)
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
                SET status = 'completed', product_count = %s, quote_count = %s,
                    finding_count = %s, vendor_status = %s::jsonb,
                    finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [len(products), quote_count, finding_count, json.dumps(vendor_status), run_id],
            )
            conn.commit()

        logger.info(
            "price_check_run_completed",
            run_id=run_id,
            products=len(products),
            quotes=quote_count,
            findings=finding_count,
        )
        return {
            "status": "completed",
            "run_id": run_id,
            "products": len(products),
            "quotes": quote_count,
            "findings": finding_count,
        }

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _select_products(conn: Any, *, limit: int) -> list[dict[str, Any]]:
        """Watched products first, then the most-purchased repeat buys."""
        rows = conn.execute(
            """
            WITH items AS (
                SELECT product_id, COUNT(*) AS purchase_count
                FROM household_purchase_items
                WHERE removed IS NOT TRUE AND product_id IS NOT NULL
                GROUP BY product_id
            ),
            last_paid AS (
                SELECT DISTINCT ON (product_id)
                       product_id, total_price, observed_date
                FROM household_product_price_observations
                WHERE source <> 'vendor_quote'
                ORDER BY product_id, observed_date DESC, created_at DESC
            )
            SELECT p.id::text, p.canonical_name, p.brand, p.package_display_label,
                   i.purchase_count, lp.total_price
            FROM household_products p
            JOIN items i ON i.product_id = p.id
            LEFT JOIN last_paid lp ON lp.product_id = p.id
            WHERE p.watched IS TRUE OR i.purchase_count >= 2
            ORDER BY p.watched DESC, i.purchase_count DESC,
                     lp.observed_date DESC NULLS LAST, p.id
            LIMIT %s
            """,
            [limit],
        ).fetchall()
        return [
            {
                "id": str(row[0]),
                "name": str(row[1] or ""),
                "brand": str(row[2]) if row[2] else None,
                "package": str(row[3]) if row[3] else None,
                "purchase_count": int(row[4] or 0),
                "last_paid": to_float(row[5]),
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
        """One vendor_quote row per product+vendor+day; re-runs update price."""
        metadata = json.dumps(
            {
                "vendor_key": vendor_key,
                "run_id": run_id,
                "title": quote.title,
                "url": quote.url,
                "confidence": quote.confidence,
            }
        )
        existing = conn.execute(
            """
            SELECT id FROM household_product_price_observations
            WHERE product_id = %s AND source = 'vendor_quote'
              AND observed_date = CURRENT_DATE
              AND merchant_id IS NOT DISTINCT FROM %s
            LIMIT 1
            """,
            [quote.product_id, merchant_id],
        ).fetchone()
        if existing is not None:
            conn.execute(
                """
                UPDATE household_product_price_observations
                SET total_price = %s, unit_price = %s, package_display_label = %s,
                    metadata = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [quote.price, quote.unit_price, quote.package_label, metadata, existing[0]],
            )
            return
        conn.execute(
            """
            INSERT INTO household_product_price_observations (
                id, product_id, merchant_id, observed_date, total_price,
                unit_price, package_display_label, source, metadata
            ) VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, 'vendor_quote', %s::jsonb)
            """,
            [
                str(uuid.uuid4()),
                quote.product_id,
                merchant_id,
                quote.price,
                quote.unit_price,
                quote.package_label,
                metadata,
            ],
        )


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


def _finding_candidates(
    products: list[dict[str, Any]],
    vendors: list[VendorAdapter],
    results: dict[str, VendorResult],
) -> list[FindingCandidate]:
    """Best (cheapest) quote per product vs what the household last paid."""
    by_product: dict[str, tuple[str, VendorQuote]] = {}
    for adapter in vendors:
        for quote in results[adapter.vendor_key].quotes:
            current = by_product.get(quote.product_id)
            if current is None or quote.price < current[1].price:
                by_product[quote.product_id] = (adapter.vendor_key, quote)
    candidates: list[FindingCandidate] = []
    for product in products:
        best = by_product.get(product["id"])
        if best is None or product.get("last_paid") is None:
            continue
        vendor_key, quote = best
        candidates.append(
            FindingCandidate(
                product_id=product["id"],
                product_name=product["name"],
                purchase_count=int(product.get("purchase_count") or 0),
                household_price=float(product["last_paid"]),
                vendor_key=vendor_key,
                vendor_price=quote.price,
                vendor_url=quote.url,
            )
        )
    return candidates


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
