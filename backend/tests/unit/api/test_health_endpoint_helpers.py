from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Response

from app.api import health_decision_data
from app.api.health import (
    STALE_MAINTENANCE_RUNS_QUERY,
    _build_automation_decision_domain,
    _build_freshness_summary_payload,
    _build_household_decision_domain,
    _build_market_data_decision_domain,
    _build_source_decision_domain,
    _summarize_decision_data_domains,
    detailed_health_check,
    get_recent_remediations,
    get_stale_maintenance_runs,
    health_check,
)
from app.utils.health_service import CheckResult, WorkerInfo


@pytest.mark.asyncio
async def test_get_recent_remediations_dedupes_tables_and_counts_occurrences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.side_effect = [
        MagicMock(
            fetchall=MagicMock(
                return_value=[
                    (
                        "data_freshness_remediation_technical_indicators",
                        datetime(2026, 3, 11, 0, 1, tzinfo=UTC),
                        "success",
                        {
                            "age_hours": 52.0,
                            "remediation_task_name": "portfolio-backfill-indicators",
                            "workflow_run_id": "run-123",
                            "trigger_status": "triggered",
                        },
                        None,
                    ),
                    (
                        "data_freshness_alert_technical_indicators",
                        datetime(2026, 3, 11, 0, 0, tzinfo=UTC),
                        "error",
                        {
                            "age_hours": 52.0,
                            "threshold_hours": 48.0,
                            "reason": "age",
                        },
                        "latest failure",
                    ),
                    (
                        "data_freshness_alert_technical_indicators",
                        datetime(2026, 3, 10, 22, 0, tzinfo=UTC),
                        "error",
                        {
                            "age_hours": 50.0,
                            "threshold_hours": 48.0,
                            "reason": "age",
                        },
                        "older failure",
                    ),
                    (
                        "data_freshness_alert_fear_greed_daily",
                        datetime(2026, 3, 10, 21, 0, tzinfo=UTC),
                        "error",
                        {
                            "age_hours": 52.0,
                            "threshold_hours": 48.0,
                            "reason": "age",
                        },
                        "another failure",
                    ),
                ]
            )
        ),
        MagicMock(
            fetchone=MagicMock(
                return_value=(
                    {
                        "fresh": 9,
                        "stale": 0,
                        "critical": 0,
                        "details": [
                            {"table_name": "technical_indicators", "is_stale": False, "is_critical": False},
                            {"table_name": "fear_greed_daily", "is_stale": False, "is_critical": False},
                        ],
                    },
                    datetime(2026, 3, 11, 1, 0, tzinfo=UTC),
                    "success",
                )
            )
        ),
    ]

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection

    monkeypatch.setattr("app.api.health.get_storage", lambda: fake_storage)

    remediations = await get_recent_remediations()

    assert [event["table_name"] for event in remediations] == [
        "technical_indicators",
        "fear_greed_daily",
    ]
    assert remediations[0]["triggered_at"] == "2026-03-11T00:01:00+00:00"
    assert remediations[0]["occurrence_count"] == 3
    assert remediations[0]["event_type"] == "remediation"
    assert remediations[0]["remediation_task_name"] == "portfolio-backfill-indicators"
    assert remediations[0]["workflow_run_id"] == "run-123"
    assert remediations[0]["trigger_status"] == "triggered"
    assert remediations[0]["error_message"] is None
    assert remediations[0]["resolved"] is True
    assert remediations[0]["resolved_at"] == "2026-03-11T01:00:00+00:00"
    assert remediations[1]["occurrence_count"] == 1
    assert remediations[1]["resolved"] is True


@pytest.mark.asyncio
async def test_get_recent_remediations_keeps_active_failures_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.side_effect = [
        MagicMock(
            fetchall=MagicMock(
                return_value=[
                    (
                        "data_freshness_alert_reference_cache",
                        datetime(2026, 3, 11, 2, 0, tzinfo=UTC),
                        "error",
                        {
                            "age_hours": 30.0,
                            "threshold_hours": 24.0,
                            "reason": "age",
                        },
                        "still stale",
                    ),
                ]
            )
        ),
        MagicMock(
            fetchone=MagicMock(
                return_value=(
                    {
                        "fresh": 8,
                        "stale": 1,
                        "critical": 0,
                        "details": [
                            {"table_name": "reference_cache", "is_stale": True, "is_critical": False},
                        ],
                    },
                    datetime(2026, 3, 11, 3, 0, tzinfo=UTC),
                    "success",
                )
            )
        ),
    ]

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection

    monkeypatch.setattr("app.api.health.get_storage", lambda: fake_storage)

    remediations = await get_recent_remediations()

    assert remediations[0]["table_name"] == "reference_cache"
    assert remediations[0]["resolved"] is False
    assert remediations[0]["resolved_at"] is None


@pytest.mark.asyncio
async def test_get_recent_remediations_resolves_recovered_table_despite_other_stale_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.side_effect = [
        MagicMock(
            fetchall=MagicMock(
                return_value=[
                    (
                        "data_freshness_alert_news_cache",
                        datetime(2026, 3, 11, 2, 0, tzinfo=UTC),
                        "error",
                        {
                            "age_hours": 30.0,
                            "threshold_hours": 24.0,
                            "reason": "age",
                        },
                        "was stale earlier",
                    ),
                ]
            )
        ),
        MagicMock(
            fetchone=MagicMock(
                return_value=(
                    {
                        "fresh": 8,
                        "stale": 1,
                        "critical": 0,
                        "details": [
                            {"table_name": "news_cache", "is_stale": False, "is_critical": False},
                            {"table_name": "reference_cache", "is_stale": True, "is_critical": False},
                        ],
                    },
                    datetime(2026, 3, 11, 3, 0, tzinfo=UTC),
                    "success",
                )
            )
        ),
    ]

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection

    monkeypatch.setattr("app.api.health.get_storage", lambda: fake_storage)

    remediations = await get_recent_remediations()

    assert remediations[0]["table_name"] == "news_cache"
    assert remediations[0]["resolved"] is True
    assert remediations[0]["resolved_at"] == "2026-03-11T03:00:00+00:00"


@pytest.mark.asyncio
async def test_get_stale_maintenance_runs_returns_old_running_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.return_value.fetchall.return_value = [
        (
            "cleanup_debug_captures",
            datetime(2026, 3, 11, 2, 15, tzinfo=UTC),
            False,
        ),
    ]

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection

    monkeypatch.setattr("app.api.health.get_storage", lambda: fake_storage)

    stale_runs = await get_stale_maintenance_runs()
    executed_sql = fake_conn.execute.call_args[0][0]

    assert stale_runs == [
        {
            "task_name": "cleanup_debug_captures",
            "started_at": "2026-03-11T02:15:00+00:00",
            "dry_run": False,
        }
    ]
    assert "NOT EXISTS" in executed_sql
    assert "newer.task_name = maintenance_log.task_name" in executed_sql
    assert executed_sql == STALE_MAINTENANCE_RUNS_QUERY


@pytest.mark.asyncio
async def test_get_data_freshness_summary_returns_no_data_when_no_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.return_value.fetchone.return_value = None

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection

    monkeypatch.setattr("app.api.health.get_storage", lambda: fake_storage)

    from app.api.health import get_data_freshness_summary

    summary = await get_data_freshness_summary()

    assert summary == {
        "last_check": None,
        "status": "no_data",
        "message": "No freshness checks have been run yet",
    }


def test_freshness_summary_escalates_successful_check_with_overdue_tables() -> None:
    payload = _build_freshness_summary_payload(
        (
            {
                "tables_checked": 10,
                "fresh": 8,
                "stale": 1,
                "critical": 1,
                "remediations_triggered": 1,
            },
            datetime(2026, 3, 11, 3, 0, tzinfo=UTC),
            "success",
        )
    )

    assert payload["status"] == "critical"
    assert payload["check_status"] == "success"
    assert payload["message"] == "1 table overdue; 1 table getting old"


def test_freshness_summary_marks_stale_tables_as_warning() -> None:
    payload = _build_freshness_summary_payload(
        (
            {
                "tables_checked": 10,
                "fresh": 9,
                "stale": 1,
                "critical": 0,
                "remediations_triggered": 0,
            },
            datetime(2026, 3, 11, 3, 0, tzinfo=UTC),
            "success",
        )
    )

    assert payload["status"] == "warning"
    assert payload["message"] == "1 table getting old"


def test_decision_data_domains_are_healthy_when_all_current() -> None:
    market = _build_market_data_decision_domain(
        {"status": "success", "message": "All checked tables are current", "fresh": 5, "stale": 0, "critical": 0}
    )
    household = _build_household_decision_domain(
        SimpleNamespace(
            generated_at="2026-04-24T13:00:00+00:00",
            overview=SimpleNamespace(
                monthly_spend_status="current",
                monthly_spend_detail="Monthly spend reflects current covered transaction accounts.",
                net_worth_status="current",
                net_worth_detail="Net worth reflects current covered accounts.",
                needs_refresh_count=0,
                gap_count=0,
                inbox_count=0,
                coverage_months=6,
                last_transaction_date="2026-04-23",
            ),
        )
    )
    automation = _build_automation_decision_domain(
        SimpleNamespace(
            status="healthy",
            total_workflows_24h=2,
            successful_workflows=2,
            failed_workflows=0,
            blocked_workflows=0,
            last_successful_workflow=datetime(2026, 4, 24, 13, 0, tzinfo=UTC),
            last_successful_type="daily_operator",
        ),
        now=datetime(2026, 4, 24, 14, 0, tzinfo=UTC),
    )
    sources = _build_source_decision_domain(
        {"polygon": SimpleNamespace(status="ok", last_success=datetime(2026, 4, 24, 13, 0, tzinfo=UTC))},
        [SimpleNamespace(source_name="Polygon", configured=True)],
    )

    health = _summarize_decision_data_domains([market, household, automation, sources])

    assert health.status == "healthy"
    assert health.message == "All decision-data domains are current."


def test_decision_data_household_marks_stale_spend_evidence() -> None:
    domain = _build_household_decision_domain(
        SimpleNamespace(
            generated_at="2026-04-24T13:00:00+00:00",
            overview=SimpleNamespace(
                monthly_spend_status="stale",
                monthly_spend_detail="2 spending accounts should refresh before review.",
                net_worth_status="current",
                needs_refresh_count=2,
                gap_count=0,
                inbox_count=1,
                coverage_months=4,
            ),
        )
    )

    assert domain.status == "stale"
    assert domain.severity == "critical"
    assert domain.evidence["needs_refresh_count"] == 2


def test_decision_data_household_warns_on_known_stale_net_worth() -> None:
    domain = _build_household_decision_domain(
        SimpleNamespace(
            generated_at="2026-04-24T13:00:00+00:00",
            overview=SimpleNamespace(
                monthly_spend_status="estimated",
                monthly_spend_detail="Monthly spend is usable with review.",
                net_worth_status="stale",
                net_worth_detail="Known net worth subtotal has stale manual balances.",
                needs_refresh_count=3,
                gap_count=2,
                inbox_count=1,
                coverage_months=4,
            ),
        )
    )

    assert domain.status == "aging"
    assert domain.severity == "warning"
    assert domain.evidence["net_worth_status"] == "stale"


def test_decision_data_automation_marks_no_runs_as_missing() -> None:
    domain = _build_automation_decision_domain(
        SimpleNamespace(
            status="healthy",
            total_workflows_24h=0,
            successful_workflows=0,
            failed_workflows=0,
            blocked_workflows=0,
            last_successful_workflow=None,
        )
    )

    assert domain.status == "missing"
    assert domain.severity == "critical"


def test_decision_data_source_marks_disabled_provider_distinctly() -> None:
    domain = _build_source_decision_domain(
        {"polygon": SimpleNamespace(status="ok", last_success=datetime(2026, 4, 24, 13, 0, tzinfo=UTC))},
        [
            SimpleNamespace(source_name="Polygon", configured=True),
            SimpleNamespace(source_name="AlphaVantage", configured=False),
        ],
    )

    assert domain.status == "disabled"
    assert domain.severity == "warning"
    assert domain.evidence["disabled_sources"] == ["AlphaVantage"]


def test_decision_data_source_marks_quota_limited_provider_distinctly() -> None:
    domain = _build_source_decision_domain(
        {
            "alphavantage": SimpleNamespace(
                status="ok",
                last_success=datetime(2026, 4, 24, 13, 0, tzinfo=UTC),
                rate_limit_hits=3,
                in_cooldown=True,
            )
        },
        [SimpleNamespace(source_name="AlphaVantage", configured=True)],
    )

    assert domain.status == "quota_limited"
    assert domain.severity == "warning"
    assert domain.evidence["quota_limited_sources"] == ["alphavantage"]


def test_decision_data_summary_reports_mixed_degraded_and_critical_domains() -> None:
    health = _summarize_decision_data_domains(
        [
            _build_market_data_decision_domain({"status": "critical", "critical": 1}),
            _build_source_decision_domain({}, [SimpleNamespace(source_name="Polygon", configured=False)]),
        ]
    )

    assert health.status == "critical"
    assert health.message == "2 of 2 decision-data domains need review."


@pytest.mark.asyncio
async def test_decision_data_health_caches_expensive_service_domains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"household": 0}
    health_decision_data._domain_cache.clear()

    async def fake_run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)

    def fake_household_domain():
        calls["household"] += 1
        return health_decision_data._decision_domain(
            key="household_evidence",
            label="Household Evidence",
            status="current",
            severity="healthy",
            message="Household current.",
        )

    workflow_health = SimpleNamespace(
        status="ok",
        total_workflows_24h=1,
        successful_workflows=1,
        failed_workflows=0,
        blocked_workflows=0,
        last_successful_workflow=datetime.now(UTC),
    )
    health_result = {
        "workflow_health": workflow_health,
        "sources": {
            "yfinance": SimpleNamespace(
                status="ok",
                status_reason="",
                rate_limit_hits=0,
                in_cooldown=False,
                last_success=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
            )
        },
        "api_quotas": [SimpleNamespace(source_name="YFinance", configured=True)],
    }

    monkeypatch.setattr(health_decision_data, "run_in_threadpool", fake_run_in_threadpool)
    monkeypatch.setattr(
        health_decision_data,
        "_household_domain_from_service",
        fake_household_domain,
    )

    try:
        first = await health_decision_data.get_decision_data_health(
            health_result=health_result,
            data_freshness_status={"status": "success", "message": "Fresh."},
        )
        second = await health_decision_data.get_decision_data_health(
            health_result=health_result,
            data_freshness_status={"status": "success", "message": "Fresh."},
        )

        assert first["status"] == "healthy"
        assert second["status"] == "healthy"
        assert calls == {"household": 1}
    finally:
        health_decision_data._domain_cache.clear()


@pytest.mark.asyncio
async def test_health_check_runs_service_in_threadpool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeHealthService:
        def perform_health_check(self) -> dict[str, object]:
            return {
                "status": "healthy",
                "uptime_seconds": 12,
                "checks": {"database": CheckResult(status="ok")},
                "sources": {},
                "services": {},
            }

    def fake_get_health_service() -> FakeHealthService:
        return FakeHealthService()

    async def fake_run_in_threadpool(func, *args, **kwargs):
        calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr("app.api.health._get_health_service", fake_get_health_service)
    monkeypatch.setattr("app.api.health.run_in_threadpool", fake_run_in_threadpool)

    payload = await health_check(Response())

    assert calls == ["perform_health_check"]
    assert payload.status == "healthy"


@pytest.mark.asyncio
async def test_detailed_health_check_runs_service_in_threadpool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeHealthService:
        def perform_detailed_health_check(self) -> dict[str, object]:
            return {
                "status": "healthy",
                "uptime_seconds": 12,
                "checks": {"database": CheckResult(status="ok")},
                "sources": {},
                "services": {},
                "day_bars_freshness": [],
                "worker": WorkerInfo(active=True),
                "api_keys": [],
            }

    def fake_get_health_service() -> FakeHealthService:
        return FakeHealthService()

    async def fake_run_in_threadpool(func, *args, **kwargs):
        calls.append(func.__name__)
        return func(*args, **kwargs)

    async def fake_get_data_freshness_summary() -> dict[str, object]:
        return {"status": "success", "last_check": None}

    async def fake_get_recent_remediations() -> list[dict[str, object]]:
        return []

    async def fake_get_stale_maintenance_runs() -> list[dict[str, object]]:
        return []

    async def fake_get_decision_data_health(**_kwargs) -> dict[str, object]:
        return {"status": "healthy", "message": "All current.", "domains": []}

    monkeypatch.setattr("app.api.health._get_health_service", fake_get_health_service)
    monkeypatch.setattr("app.api.health.run_in_threadpool", fake_run_in_threadpool)
    monkeypatch.setattr("app.api.health.get_data_freshness_summary", fake_get_data_freshness_summary)
    monkeypatch.setattr("app.api.health.get_decision_data_health", fake_get_decision_data_health)
    monkeypatch.setattr("app.api.health.get_recent_remediations", fake_get_recent_remediations)
    monkeypatch.setattr("app.api.health.get_stale_maintenance_runs", fake_get_stale_maintenance_runs)

    payload = await detailed_health_check(Response())

    assert calls == ["perform_detailed_health_check"]
    assert payload.status == "healthy"


def test_build_deletion_rate_message_uses_threshold_bands() -> None:
    from app.api.health import _build_deletion_rate_message

    assert _build_deletion_rate_message(0, 1) == ("ok", "✅ OK: 0 deletions in last 1h")
    assert _build_deletion_rate_message(10, 4) == (
        "warning",
        "⚠️  WARNING: 10 deletions in last 4h (threshold: 10)",
    )
    assert _build_deletion_rate_message(100, 2) == (
        "critical",
        "🔴 CRITICAL: 100 deletions in last 2h (threshold: 100)",
    )
