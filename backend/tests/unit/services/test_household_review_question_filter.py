"""Questions existing data already answers are not asked again."""

from __future__ import annotations

from typing import Any

from app.services._household_review_question_filter import (
    drop_settled_questions,
    merchant_match_token,
)

_CHANNEL = {"question": "Is Walmart a recurring household shopping channel?"}
_CORE = {
    "question": "Should Jenny treat CHASEVISA-9728 as part of core household spending?",
    "field_name": "monthly_essential_target",
}
_RETIREMENT = {
    "question": "Should this account count toward retirement readiness tracking?",
    "field_name": "target_retirement_spend",
}
_UNKNOWN = {"question": "What kind of document is this and which account or merchant is it tied to?"}


class _Result:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(
        self,
        *,
        answered: list[tuple[Any, ...]] | None = None,
        merchant_history: tuple[int, int] = (0, 0),
        accounts: list[tuple[Any, ...]] | None = None,
        account_spend: tuple[int, int] = (0, 0),
    ) -> None:
        self.answered = answered or []
        self.merchant_history = merchant_history
        self.accounts = accounts or []
        self.account_spend = account_spend

    def execute(self, sql: str, params: list[Any] | None = None) -> _Result:
        if "FROM household_questions" in sql:
            return _Result(self.answered)
        if "FROM household_accounts" in sql:
            return _Result(self.accounts)
        if "household_account_id = %s" in sql:
            return _Result([self.account_spend])
        return _Result([self.merchant_history])


def _receipt(*questions: dict[str, Any], **structured: Any) -> dict[str, Any]:
    return {
        "questions": list(questions),
        "structured_data": structured,
        "review_checks": {"ambiguity_remaining": True, "ambiguity_reason": questions[0]["question"]},
    }


def test_merchant_token_ignores_store_numbers_and_generic_words() -> None:
    assert merchant_match_token("Costco Wholesale #336") == "costco"
    assert merchant_match_token("Walmart (Store #5831, Largo, FL)") == "walmart"


def test_prior_answer_for_the_merchant_settles_the_question() -> None:
    conn = _Conn(answered=[("Is Walmart a recurring household shopping channel?", None, "Walmart", None)])
    reviewed = _receipt(_CHANNEL, merchant="Walmart")
    assert drop_settled_questions(conn, reviewed) == [_CHANNEL["question"]]
    assert reviewed["questions"] == []
    # The blocker that only restated the question is released for re-evaluation.
    assert reviewed["review_checks"]["ambiguity_remaining"] is None


def test_ledger_history_answers_a_new_merchant_question() -> None:
    reviewed = _receipt(_CHANNEL, merchant="Walmart")
    assert drop_settled_questions(_Conn(merchant_history=(96, 12)), reviewed)
    assert reviewed["questions"] == []


def test_a_genuinely_new_merchant_is_still_asked() -> None:
    reviewed = _receipt(_CHANNEL, merchant="Walmart")
    assert drop_settled_questions(_Conn(merchant_history=(1, 1)), reviewed) == []
    assert reviewed["questions"] == [_CHANNEL]
    assert reviewed["review_checks"]["ambiguity_remaining"] is True


def test_account_with_recorded_spend_is_already_core_spending() -> None:
    conn = _Conn(accounts=[("acct-1", "credit", "credit_card")], account_spend=(929, 12))
    reviewed = _receipt(_CORE, account_hint="CHASEVISA-9728")
    assert drop_settled_questions(conn, reviewed) == [_CORE["question"]]


def test_account_without_history_is_still_asked_about_core_spending() -> None:
    conn = _Conn(accounts=[("acct-1", "credit", "credit_card")], account_spend=(2, 1))
    reviewed = _receipt(_CORE, account_hint="CHASEVISA-9728")
    assert drop_settled_questions(conn, reviewed) == []


def test_account_type_answers_retirement_tracking() -> None:
    ira = _Conn(accounts=[("acct-2", "retirement", "ira")])
    assert drop_settled_questions(ira, _receipt(_RETIREMENT, account_hint="Rollover IRA *8698"))
    taxable = _Conn(accounts=[("acct-3", "taxable", "brokerage")])
    assert drop_settled_questions(taxable, _receipt(_RETIREMENT, account_hint="Individual *7544")) == []


def test_ambiguous_account_match_does_not_guess() -> None:
    conn = _Conn(accounts=[("a", "retirement", "ira"), ("b", "taxable", "brokerage")])
    assert drop_settled_questions(conn, _receipt(_RETIREMENT, account_hint="*1234")) == []


def test_unrelated_questions_and_duplicates() -> None:
    reviewed = _receipt(_UNKNOWN, dict(_UNKNOWN))
    dropped = drop_settled_questions(_Conn(), reviewed)
    assert dropped == [_UNKNOWN["question"]]
    assert reviewed["questions"] == [_UNKNOWN]
