from app.services.household_evidence_source import receipt_arithmetic
from app.services.household_identity import capture_path_allowed


def test_arithmetic_preserves_zero_and_folds_only_actual_discounts():
    rows = receipt_arithmetic(
        {
            "transactions": [
                {
                    "merchant": "Store",
                    "line_items": [{"description": "Item", "amount": 12}, {"description": "Item", "amount": -2}],
                    "subtotal": 10,
                    "tax": 1,
                    "amount": 11,
                },
                {
                    "line_items": [{"description": "Item", "amount": 5, "discount": 5}],
                    "subtotal": 0,
                    "subtotal_amount": 99,
                    "tax": 0,
                    "amount": 0,
                    "total_amount": 99,
                },
                {"line_items": [{"description": "Item", "amount": 5}], "subtotal": 8, "tax": 1, "amount": 10},
            ]
        }
    )
    assert rows[0]["line_total"] == 10
    assert rows[0]["line_difference"] == rows[0]["total_difference"] == 0
    assert rows[1]["subtotal"] == rows[1]["total"] == 0
    assert rows[1]["line_difference"] == rows[1]["total_difference"] == 0
    assert rows[2]["line_difference"] == -3
    assert rows[2]["total_difference"] == -1


def test_invalid_arithmetic_is_not_published_as_zero_or_balanced():
    assert receipt_arithmetic({"line_items": [{"description": "Item", "amount": "NaN"}]}) == []
    result = receipt_arithmetic({"line_items": [{"description": "Unreadable amount"}]})
    assert result[0]["line_total"] is None
    assert result[0]["total_difference"] is None


def test_evidence_sources_are_not_in_child_capture_allowlist():
    assert not capture_path_allowed("GET", "/api/intake/evidence/document/source")
    assert not capture_path_allowed("GET", "/api/intake/evidence/document/file")


def test_inference_refresh_preserves_confirmed_and_dismissed_values():
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.services._household_dashboard_profile_inference import upsert_transaction_inference

    for status in ['confirmed', 'dismissed']:
        conn = Mock()
        assert not upsert_transaction_inference(
            conn, field_name='monthly_essential_target', value=99,confidence=1,
            rationale='New observation',profile=SimpleNamespace(monthly_essential_target=None),
            existing_inferences={'monthly_essential_target':{'status':status,'source':'transaction_inference','value':200}},
        )
        conn.execute.assert_not_called()
