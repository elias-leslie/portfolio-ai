"""Coverage has to move with what the system can see, not with what it was told.

`visibility_score` reported 99 / "Strong household visibility" while net worth
was stale, three accounts needed refreshing and a spending feed had gone quiet.
It scored 99 because it was a setup checklist -- points for having *told* the
system a retirement age. Answering a question is not the same as being visible,
so the confidence signal moved opposite to the actual coverage.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services._household_coverage import build_coverage


def _account(
    *,
    label: str = "Checking",
    current_value: float = 1000.0,
    money_role: str = "net_worth_only",
    freshness_status: str = "fresh",
    balance_freshness_status: str | None = None,
    transaction_freshness_status: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        label=label,
        current_value=current_value,
        money_role=money_role,
        freshness_status=freshness_status,
        balance_freshness_status=balance_freshness_status or freshness_status,
        transaction_freshness_status=transaction_freshness_status or freshness_status,
    )


def _coverage(accounts, discovered=(), *, expenses=100, unclassified=0):
    return build_coverage(
        account_summaries=list(accounts),
        discovered_accounts=list(discovered),
        tracked_expense_count=expenses,
        unclassified_count=unclassified,
    )


def test_telling_the_system_a_retirement_age_no_longer_scores_as_visibility() -> None:
    """The old score awarded 80 of its 100 points before seeing one account."""
    coverage = _coverage([], expenses=0)

    assert coverage.score == 0
    assert coverage.label == "Limited coverage"


def test_a_fully_connected_current_household_scores_full_marks() -> None:
    coverage = _coverage(
        [
            _account(money_role="spend_driver"),
            _account(current_value=500_000.0),
        ]
    )

    assert coverage.score == 100
    assert coverage.label == "Strong coverage"
    assert "connected, current and classified" in coverage.summary


def test_stale_balances_are_weighted_by_money_not_by_account() -> None:
    """A $572,782 brokerage going stale is not the same event as a $0 rollover.

    Counting accounts would call them equal, which is how a score stays high
    while the number people actually read goes wrong.
    """
    big_stale = _coverage(
        [
            _account(current_value=900_000.0, freshness_status="stale"),
            _account(current_value=100_000.0),
            _account(money_role="spend_driver", current_value=1000.0),
        ]
    )
    small_stale = _coverage(
        [
            _account(current_value=900_000.0),
            _account(current_value=100_000.0, freshness_status="stale"),
            _account(money_role="spend_driver", current_value=1000.0),
        ]
    )

    big_balance = next(c for c in big_stale.components if c.key == "balances")
    small_balance = next(c for c in small_stale.components if c.key == "balances")
    assert big_balance.score < small_balance.score
    assert big_stale.score < small_stale.score


def test_a_quiet_spending_feed_pulls_the_score_down_and_is_named() -> None:
    coverage = _coverage(
        [
            _account(label="Joint checking", money_role="spend_driver"),
            _account(
                label="Sapphire ·8054",
                money_role="spend_driver",
                transaction_freshness_status="stale",
            ),
        ]
    )

    feeds = next(c for c in coverage.components if c.key == "spending_feeds")
    assert feeds.score == 50
    assert "Sapphire ·8054" in feeds.detail
    assert coverage.score < 100


def test_an_account_seen_in_evidence_but_not_connected_is_a_coverage_hole() -> None:
    """The ·4635 card is named on five receipts and matches no account.

    No amount of freshness on the other accounts fills that in, so it has to
    cost something.
    """
    connected_only = _coverage([_account(money_role="spend_driver")])
    with_gap = _coverage(
        [_account(money_role="spend_driver")],
        [SimpleNamespace(suggested_label="Visa Credit ****4635", key="unlinked_4635")],
    )

    assert with_gap.score < connected_only.score
    linked = next(c for c in with_gap.components if c.key == "connected_accounts")
    assert linked.score == 50
    assert "4635" in linked.detail


def test_spend_waiting_on_a_category_is_counted_as_not_yet_visible() -> None:
    coverage = _coverage(
        [_account(money_role="spend_driver")], expenses=200, unclassified=50
    )

    classified = next(c for c in coverage.components if c.key == "classified_spend")
    assert classified.score == 75
    assert "50 of 200 expense rows" in classified.detail


def test_the_score_is_the_weighted_mean_of_its_published_components() -> None:
    """Publishing the working is what makes the number checkable.

    A single figure that cannot be broken down is exactly how "99% visibility"
    survived beside a stale net worth for as long as it did.
    """
    coverage = _coverage(
        [
            _account(money_role="spend_driver"),
            _account(current_value=1000.0, freshness_status="stale"),
        ],
        expenses=100,
        unclassified=10,
    )

    total_weight = sum(component.weight for component in coverage.components)
    expected = round(
        sum(c.score * c.weight for c in coverage.components) / total_weight
    )
    assert coverage.score == expected
    assert total_weight == 100
    assert {c.key for c in coverage.components} == {
        "balances",
        "spending_feeds",
        "connected_accounts",
        "classified_spend",
    }


def test_the_summary_names_the_weakest_component_rather_than_the_score() -> None:
    """"84%" tells nobody what to do; "two accounts are stale" does."""
    coverage = _coverage(
        [
            _account(label="Joint checking", money_role="spend_driver"),
            _account(
                label="Sapphire ·8054",
                money_role="spend_driver",
                transaction_freshness_status="stale",
            ),
            _account(
                label="Sapphire ·3627",
                money_role="spend_driver",
                transaction_freshness_status="stale",
            ),
        ]
    )

    assert "gone quiet" in coverage.summary
    assert coverage.summary.startswith(coverage.label)


def test_a_household_with_no_spending_feed_at_all_says_so() -> None:
    coverage = _coverage([_account(current_value=250_000.0)])

    feeds = next(c for c in coverage.components if c.key == "spending_feeds")
    assert feeds.score == 0
    assert feeds.detail == "No account is currently reporting transactions."


def test_a_small_problem_still_stops_a_component_reading_perfect() -> None:
    """$6,793 stale against $1.56M rounds to 100% and must not print as 100.

    A perfect score directly above a line naming two stale accounts is the
    anti-correlation this module exists to remove. Small is not absent.
    """
    coverage = _coverage(
        [
            _account(current_value=1_554_220.0),
            _account(current_value=6_793.0, freshness_status="stale"),
            _account(money_role="spend_driver", current_value=1000.0),
        ]
    )

    balances = next(c for c in coverage.components if c.key == "balances")
    assert balances.score == 99
    assert "1 of 3 accounts is stale" in balances.detail


def test_one_quiet_feed_reads_as_singular() -> None:
    coverage = _coverage(
        [
            _account(label="Joint checking", money_role="spend_driver"),
            _account(
                label="Sapphire ·8054",
                money_role="spend_driver",
                transaction_freshness_status="stale",
            ),
        ]
    )

    feeds = next(c for c in coverage.components if c.key == "spending_feeds")
    assert "1 of 2 spending accounts has gone quiet" in feeds.detail
