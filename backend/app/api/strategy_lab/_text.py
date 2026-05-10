from __future__ import annotations

from .models import StrategyLabPrimaryAccountTarget

STALE_HELPER_TEXT = "Quote is stale. Refresh market data before acting."
INSUFFICIENT_HISTORY_TEXT = "Not enough daily history to judge this strategy yet."
NO_TRADES_TEXT = "This strategy produced no trades over the test window."
STALE_WHY_BULLETS = [
    "Quote is stale.",
    "Refresh market data before acting.",
    "Strategy details are unavailable until fresh pricing returns.",
]
STALE_WATCH_ITEM = "Refresh and re-check this symbol during market hours."


def _healthy_why_bullets(
    action: str,
    held: bool,
    account: StrategyLabPrimaryAccountTarget | None,
    pullback: bool,
    breakout: bool,
    sma_200: float | None,
) -> list[str]:
    if pullback:
        price = "Price setup: pullback trigger is active."
    elif breakout and not held:
        price = "Price setup: breakout trigger is active."
    else:
        price = "Price setup: no entry trigger is active."

    if sma_200 is None:
        market = "Market context: unavailable."
    elif pullback:
        market = "Market context: price is still above the 200-day trend."
    elif breakout and not held:
        market = "Market context: price is above the 50-day and 200-day trend filters."
    else:
        market = "Market context: trend filters are not confirming a new entry."

    if account is None:
        account_text = "Account context: unavailable."
    elif held:
        account_text = f"Account context: already held in {account.account_name}."
    elif action in {"buy_now", "buy_in_stages"}:
        account_text = f"Account context: {account.account_name} is the current target account."
    else:
        account_text = "Account context: unavailable."

    return [price, market, account_text]


def _watch_item(action: str, held: bool, pullback: bool, breakout: bool) -> str:
    if pullback and action == "buy_in_stages":
        return "Watch: if the pullback deepens, reassess the next staged buy."
    if breakout and action == "buy_now":
        return "Watch: if the breakout fails, stand aside and reassess."
    if held:
        return "Watch: wait for the pullback trigger to reactivate."
    return "Watch: wait for a qualifying pullback or breakout."


def _stale_template(held: bool) -> str:
    return "pullback_accumulator" if held else "breakout_confirmation"
