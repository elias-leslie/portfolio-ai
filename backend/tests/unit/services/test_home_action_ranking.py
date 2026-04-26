"""Unit tests for home action ranking metadata."""

from __future__ import annotations

from types import SimpleNamespace

from app.services._home_action_ranking import household_rank_metadata


def test_household_rank_metadata_scores_account_transaction_freshness() -> None:
    metadata = household_rank_metadata(
        SimpleNamespace(
            id="account-1-stale_transactions",
            priority="high",
            action_href="/money?tab=accounts&account=1&intent=evidence",
            detail="Blocks monthly spend, budget status, and safe to spend.",
        )
    )

    assert metadata["_rank_score"] == 2390.0
    assert metadata["urgency_score"] == 2000.0
    assert metadata["impact_score"] == 260.0
    assert metadata["freshness_score"] == 200.0
    assert metadata["effort_score"] == 70.0


def test_household_rank_metadata_scores_account_balance_freshness() -> None:
    metadata = household_rank_metadata(
        SimpleNamespace(
            id="account-1-stale_balance",
            priority="high",
            action_href="/money?tab=accounts&account=1&intent=evidence",
            detail="Blocks net worth.",
        )
    )

    assert metadata["_rank_score"] == 2340.0
    assert metadata["impact_score"] == 220.0
    assert metadata["freshness_score"] == 160.0
    assert metadata["effort_score"] == 40.0


def test_household_rank_metadata_scores_transaction_date_quality() -> None:
    metadata = household_rank_metadata(
        SimpleNamespace(
            id="cashflow-future-transaction-dates",
            priority="high",
            action_href="/money?tab=intake&focus=date-quality",
            detail="Future-dated transactions are held out.",
        )
    )

    assert metadata["_rank_score"] == 2370.0
    assert metadata["impact_score"] == 260.0
    assert metadata["freshness_score"] == 180.0
    assert metadata["effort_score"] == 70.0


def test_household_rank_metadata_scores_document_upload_needs() -> None:
    metadata = household_rank_metadata(
        SimpleNamespace(
            id="need_document_tax_return",
            priority="high",
            action_href="/money?tab=intake",
            detail="Tax documents support planning assumptions.",
        )
    )

    assert metadata["_rank_score"] == 2240.0
    assert metadata["impact_score"] == 190.0
    assert metadata["freshness_score"] == 120.0
    assert metadata["effort_score"] == 70.0
