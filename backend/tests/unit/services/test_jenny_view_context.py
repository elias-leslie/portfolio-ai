from types import SimpleNamespace
from unittest.mock import Mock

from app.services._jenny_conversation_context import build_compact_context
from app.services._jenny_view_context import build_view_context, current_symbol


def test_current_symbol_comes_only_from_a_supported_symbol_route():
    assert current_symbol({"pathname": "/symbols/aapl"}) == "AAPL"
    assert current_symbol({"pathname": "/money", "search": "?symbol=AAPL"}) is None
    assert current_symbol({"pathname": "/symbols/AAPL/../../other"}) is None


def test_selected_month_and_canonical_funding_survive_compaction():
    service = Mock()
    snapshot = {
        "generated_at": "2026-09-11T12:00:00Z",
        "summary": {"month": "2026-08", "total_spend": 125, "coverage_status": "partial"},
        "review_plan": {"planned_asset_draw": 50, "expected_income": 75},
        "categories": [{"category": "Food & dining", "total_spend": 125}],
    }
    service.get_spending.return_value = SimpleNamespace(
        summary=SimpleNamespace(month="2026-08"),
        model_dump=lambda **_: snapshot,
    )
    view = build_view_context(
        {"pathname": "/money", "search": "?tab=spending&month=2026-08"}, service
    )
    service.get_spending.assert_called_once_with(month="2026-08")
    compact = build_compact_context({"household": {}, "current_view": view})
    assert compact["current_view"]["summary"] == snapshot["summary"]
    assert compact["current_view"]["review_plan"] == snapshot["review_plan"]
    link = compact["current_view"]["evidence_links"]["category_transactions"]["Food & dining"]
    assert "month=2026-08" in link and "ledgerInclusion=included" in link
    assert "ledgerCategory=Food+%26+dining" in link


def test_invalid_month_or_unrelated_page_does_not_fetch_financial_review():
    service = Mock()
    assert build_view_context({"pathname": "/other", "search": "?month=2026-08"}, service) is None
    invalid = build_view_context({"pathname": "/money", "search": "?month=2026-99"}, service)
    assert invalid is not None and invalid["status"] == "unavailable"
    service.get_spending.assert_not_called()


def test_retirement_does_not_claim_saved_inputs_are_current_browser_scenario():
    service = Mock()
    view = build_view_context({"pathname": "/money", "search": "?tab=retirement"}, service)
    assert view is not None and "overrides" in view["source"]
    service.get_spending.assert_not_called()


def test_failed_review_remains_unavailable_instead_of_falling_back_to_another_month():
    service = Mock()
    service.get_spending.side_effect = RuntimeError("temporarily unavailable")
    view = build_view_context({"pathname": "/money", "search": "?month=2026-08"}, service)
    assert view is not None and view["status"] == "unavailable"
    service.get_spending.assert_called_once_with(month="2026-08")
