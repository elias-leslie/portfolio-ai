"""Explain existing model inputs without inventing another score or agent opinion."""

from __future__ import annotations

import math

from .models import SymbolIntelligenceResponse


def _number(value: object) -> float | None:
    if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def attach_decision_evidence(response: SymbolIntelligenceResponse) -> None:
    decision = response.decision
    if decision is None:
        return
    drivers: list[str] = []
    missing = [issue.message for issue in response.section_issues]
    triggers: list[str] = []
    scores = response.scores
    if scores:
        for name, pillar in scores.pillars.items():
            if pillar.score is None or pillar.stale:
                missing.append(
                    f"{name.replace('_', ' ').capitalize()} evidence is {'stale' if pillar.stale else 'unavailable'}."
                )
        technical = scores.pillars.get("technical")
        if technical and technical.score is not None and not technical.stale:
            metadata = technical.metadata or {}
            rsi = _number(metadata.get("rsi_14"))
            macd = _number(metadata.get("macd"))
            macd_signal = _number(metadata.get("macd_signal"))
            if rsi is not None:
                drivers.append(
                    f"RSI is {rsi:.1f}; this is a momentum indicator, not a success probability."
                )
            if macd is not None and macd_signal is not None:
                drivers.append(
                    f"MACD {macd:.2f} is {'above' if macd > macd_signal else 'at or below'} its {macd_signal:.2f} signal line."
                )
                triggers.append(
                    f"Revisit when MACD crosses {'below' if macd > macd_signal else 'above'} its signal line."
                )
            if metadata.get("vwap_missing"):
                missing.append("VWAP is missing from the technical inputs.")
            if (
                response.trends
                and response.trends.short_term_aligned is not None
                and response.trends.long_term_aligned is not None
            ):
                short, long = response.trends.short_term_aligned, response.trends.long_term_aligned
                drivers.append(
                    f"Short-term trend is {'aligned' if short else 'not aligned'}; long-term trend is {'aligned' if long else 'not aligned'}."
                )
        fundamental = scores.pillars.get("fundamental")
        if fundamental and not fundamental.stale:
            growth = _number((fundamental.metadata or {}).get("revenue_growth"))
            if growth is not None:
                drivers.append(f"Latest reported revenue growth is {growth * 100:.1f}%.")
    if response.signal and response.signal.reasons:
        reasons = [
            reason
            for values in response.signal.reasons.values()
            for reason in values
            if reason.strip()
        ]
        drivers = list(dict.fromkeys([*reasons, *drivers]))
    if (
        response.company
        and response.company.earnings_days_away is not None
        and response.company.earnings_days_away >= 0
    ):
        triggers.append(
            f"Review the earnings release due {response.company.earnings_date or 'next'} ({response.company.earnings_days_away} days)."
        )
    else:
        missing.append("The next earnings date is not confirmed.")
        triggers.append(
            "Revisit after the next company earnings release updates the fundamental evidence."
        )
    if response.quote is None or response.quote.price is None:
        missing.append("A current price is unavailable.")
    elif response.quote.freshness_status != "fresh":
        missing.append(f"Price evidence: {response.quote.freshness_label}.")
    if missing:
        triggers.insert(
            0, "Refresh the missing or stale inputs below before relying on a new entry decision."
        )
    decision.drivers = drivers[:4]
    decision.missing_evidence = list(dict.fromkeys(missing))[:6]
    decision.review_triggers = list(dict.fromkeys(triggers))[:3]
    if response.portfolio is None:
        decision.portfolio_relevance = "Account exposure did not load; position status is unknown."
    elif not response.portfolio.held:
        decision.portfolio_relevance = "Not held in the current account scope. This decision concerns a potential new position."
        if (
            decision.action.upper() == "WATCH"
            and response.signal
            and response.signal.type == "HOLD"
        ):
            decision.portfolio_relevance += " Watch is the entry action; Hold is the underlying model signal, not an instruction to hold shares you own."
    else:
        decision.portfolio_relevance = "Held in the current account scope. Review position size, look-through exposure and lot consequences before a sale."
    if decision.source_kind == "live_signal_model":
        decision.source_label = "Model evidence"
        decision.reasoning = decision.drivers or [
            "The model did not retain enough underlying evidence to explain this signal."
        ]
        decision.summary = (
            "Track a potential entry while the model signal remains Hold."
            if decision.action.upper() == "WATCH"
            and response.signal
            and response.signal.type == "HOLD"
            else "The existing model signal is shown with its current inputs and evidence gaps below."
        )
