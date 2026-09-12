"""The evaluation must catch fabrications without consuming model tokens."""

import json

from scripts.evaluate_financial_grounding import (
    CASES,
    batch_message,
    grade_batch,
    grade_reconciliation,
    same_value,
)


def correct_answers():
    return {"answers": [
        {"id": c["id"], "value": c["expected"], "sources": c["sources"], "explanation": "Supported by the supplied evidence."}
        for c in CASES
    ]}


def test_hidden_answers_are_not_in_model_payload():
    assert '"expected"' not in batch_message()


def test_correct_fixture_passes_but_wrong_owner_and_fabricated_citation_fail():
    payload = correct_answers()
    assert all(row["passed"] for row in grade_batch(json.dumps(payload)))
    payload["answers"][0]["value"] = "Jordan"
    payload["answers"][1]["sources"] = ["invented-source"]
    results = grade_batch(json.dumps(payload))
    assert not results[0]["passed"]
    assert not results[1]["passed"]


def test_malformed_duplicate_missing_and_extra_cases_cannot_pass():
    assert not any(row["passed"] for row in grade_batch("not json"))
    payload = correct_answers()
    payload["answers"].append(payload["answers"][0])
    assert not any(row["passed"] for row in grade_batch(json.dumps(payload)))
    assert not any(row["passed"] for row in grade_batch('{"answers":[]}'))


def test_unknown_is_not_zero_and_false_is_not_numeric_zero():
    assert not same_value(0, None)
    assert not same_value(0, False)
    assert not same_value(False, 0)
    assert not same_value({"profile_updates": {"target_retirement_age": 55}}, {"profile_updates": {}})


def test_missing_null_value_and_missing_explanation_fail():
    payload = correct_answers()
    del payload["answers"][4]["value"]
    del payload["answers"][0]["explanation"]
    results = grade_batch(json.dumps(payload))
    assert not results[4]["passed"]
    assert not results[0]["passed"]


def test_reconciliation_accepts_supported_answer_without_accepting_other_claims():
    assert grade_reconciliation([{"question_id": "shopping-q", "answer_text": "Yes"}])
    assert grade_reconciliation([{"question_id": "shopping-q", "answer_text": "Yes, we regularly shop at Warehouse Mart."}])
    assert not grade_reconciliation([{"question_id": "shopping-q", "answer_text": "Yes, everything is essential"}])
    assert not grade_reconciliation([{"question_id": "owner-q", "answer_text": "Yes"}])
    assert not grade_reconciliation([])
