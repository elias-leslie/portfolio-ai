"""Pure helpers for Jenny scorecards and aggregate reviews."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

from app.models.jenny import (
    JennyAgentEvaluation,
    JennyAgentScorecard,
    JennySymbolReview,
    JennyTradeReview,
)
from app.models.thesis import Thesis


@dataclass
class _ScorecardMetrics:
    win_rate: float | None
    avg_return: float | None
    agreement_rate: float | None
    calibration_score: float | None
    entry_quality_score: float | None
    risk_judgment_score: float | None
    exit_timing_score: float | None
    alert_discipline_score: float | None


def _pick_verdict(counts: Counter[str], priority: dict[str, int]) -> str:
    """Return the highest-weighted verdict from a counter."""
    return sorted(
        counts,
        key=lambda v: (counts[v], priority.get(v, 0)),
        reverse=True,
    )[0]


def _normalize_evaluation(
    evaluation: dict[str, object],
    symbol: str,
    thesis: Thesis | None,
    now_iso: str,
) -> JennyAgentEvaluation:
    """Build a transient JennyAgentEvaluation from a raw dict."""
    return JennyAgentEvaluation(
        id=str(uuid.uuid4()),
        routine_id="transient",
        symbol=symbol,
        agent_name=str(evaluation["agent_name"]),
        provider=evaluation.get("provider"),
        model=evaluation.get("model"),
        verdict=str(evaluation["verdict"]),
        confidence=evaluation.get("confidence"),
        rationale=str(evaluation["rationale"]),
        recommendation=evaluation.get("recommendation"),
        strengths=list(evaluation.get("strengths", [])),
        weaknesses=list(evaluation.get("weaknesses", [])),
        thesis_id=thesis.id if thesis else None,
        agent_run_id=evaluation.get("agent_run_id"),
        created_at=now_iso,
        metadata=evaluation.get("metadata", {}),
    )


def aggregate_symbol_review(
    *,
    symbol: str,
    evaluations: list[dict[str, object]] | list[JennyAgentEvaluation],
    thesis: Thesis | None,
    final_verdict_priority: dict[str, int],
    now_iso: str,
) -> JennySymbolReview:
    normalized: list[JennyAgentEvaluation] = []
    for evaluation in evaluations:
        if isinstance(evaluation, JennyAgentEvaluation):
            normalized.append(evaluation)
        else:
            normalized.append(_normalize_evaluation(evaluation, symbol, thesis, now_iso))

    verdict_counts: Counter[str] = Counter(e.verdict for e in normalized)
    final_verdict = _pick_verdict(verdict_counts, final_verdict_priority) if verdict_counts else "review"
    confidences = [e.confidence for e in normalized if e.confidence is not None]
    reasons = [e.rationale for e in normalized[:3]]

    return JennySymbolReview(
        symbol=symbol,
        final_verdict=final_verdict,
        average_confidence=(sum(confidences) / len(confidences)) if confidences else None,
        thesis_status=thesis.status.value if thesis else None,
        thesis_action=thesis.action.value if thesis else None,
        management_action=None,
        management_detail=None,
        position_gain_pct=None,
        position_weight_pct=None,
        reasons=reasons,
        evaluations=normalized,
    )


def _compute_agreement_and_calibration(
    evaluations: list[JennyAgentEvaluation],
    linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
    final_verdict_priority: dict[str, int],
) -> tuple[float | None, float | None]:
    """Return (agreement_rate, calibration_score) across all evaluations."""
    if not evaluations:
        return None, None

    grouped: dict[str, list[JennyAgentEvaluation]] = defaultdict(list)
    for evaluation in evaluations:
        grouped[evaluation.symbol].append(evaluation)

    agreement_hits = 0
    calibration_scores: list[float] = []
    for symbol_evals in grouped.values():
        counts: Counter[str] = Counter(e.verdict for e in symbol_evals)
        final = _pick_verdict(counts, final_verdict_priority)
        for evaluation in symbol_evals:
            if evaluation.verdict == final:
                agreement_hits += 1
            linked_review = next(
                (r for cand, r in linked_pairs if cand.id == evaluation.id), None
            )
            if linked_review and evaluation.confidence is not None:
                realized = 100.0 if (linked_review.return_pct or 0.0) > 0 else 0.0
                calibration_scores.append(
                    max(0.0, 100.0 - abs(evaluation.confidence * 100.0 - realized))
                )

    agreement_rate = agreement_hits / len(evaluations)
    calibration_score = sum(calibration_scores) / len(calibration_scores) if calibration_scores else None
    return agreement_rate, calibration_score


def _compute_scorecard_metrics(
    agent_name: str,
    evaluations: list[JennyAgentEvaluation],
    linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
    final_verdict_priority: dict[str, int],
    positive_verdicts: set[str],
) -> _ScorecardMetrics:
    """Compute all numeric scoring metrics from linked evaluation-review pairs."""
    unique_reviews = list({r.id: r for _, r in linked_pairs}.values())
    completed = len(unique_reviews)
    avg_return = (
        sum((r.return_pct or 0.0) for r in unique_reviews) / completed if completed else None
    )
    win_rate = (
        sum(1 for r in unique_reviews if (r.return_pct or 0.0) > 0) / completed
        if completed else None
    )
    agreement_rate, calibration_score = _compute_agreement_and_calibration(
        evaluations, linked_pairs, final_verdict_priority
    )
    return _ScorecardMetrics(
        win_rate=win_rate,
        avg_return=avg_return,
        agreement_rate=agreement_rate,
        calibration_score=calibration_score,
        entry_quality_score=score_entry_quality(linked_pairs, positive_verdicts),
        risk_judgment_score=score_risk_judgment(linked_pairs),
        exit_timing_score=score_exit_timing(agent_name, linked_pairs),
        alert_discipline_score=score_alert_discipline(linked_pairs, positive_verdicts),
    )


def build_scorecard(
    *,
    agent_name: str,
    evaluations: list[JennyAgentEvaluation],
    reviews_by_symbol: dict[str, list[JennyTradeReview]],
    final_verdict_priority: dict[str, int],
    positive_verdicts: set[str],
    now_iso: str,
) -> JennyAgentScorecard:
    total_evaluations = len(evaluations)
    positive_verdict_count = sum(1 for e in evaluations if e.verdict in positive_verdicts)
    linked_pairs = link_evaluations_to_reviews(evaluations, reviews_by_symbol)
    completed_reviews = len({r.id for _, r in linked_pairs})
    m = _compute_scorecard_metrics(
        agent_name, evaluations, linked_pairs, final_verdict_priority, positive_verdicts
    )
    strengths, weaknesses = summarize_scorecard(
        win_rate=m.win_rate,
        avg_return=m.avg_return,
        agreement_rate=m.agreement_rate,
        calibration_score=m.calibration_score,
        entry_quality_score=m.entry_quality_score,
        risk_judgment_score=m.risk_judgment_score,
        exit_timing_score=m.exit_timing_score,
        alert_discipline_score=m.alert_discipline_score,
    )
    last_evaluation_at = max((e.created_at for e in evaluations), default=None)
    return JennyAgentScorecard(
        agent_name=agent_name,
        total_evaluations=total_evaluations,
        completed_reviews=completed_reviews,
        positive_verdicts=positive_verdict_count,
        win_rate=m.win_rate,
        avg_return_pct=m.avg_return,
        agreement_rate=m.agreement_rate,
        calibration_score=m.calibration_score,
        entry_quality_score=m.entry_quality_score,
        risk_judgment_score=m.risk_judgment_score,
        exit_timing_score=m.exit_timing_score,
        alert_discipline_score=m.alert_discipline_score,
        strengths=strengths,
        weaknesses=weaknesses,
        last_evaluation_at=last_evaluation_at,
        updated_at=now_iso,
    )


_SCORE_RULES: list[
    tuple[str, float | None, float | None, str, str]
] = [
    # name          good_at  bad_at  strength_msg                                                         weakness_msg
    ("win_rate",    0.55,    None,   "Its reviewed symbols have produced more winners than losers.",      "Its reviewed symbols have not cleared a strong win rate yet."),
    ("avg_return",  5.0,     0.0,    "The average reviewed outcome has produced meaningful upside.",     "Average reviewed outcomes are still negative."),
    ("agreement",   0.6,     None,   "It usually aligns with the final multi-agent verdict.",             "It frequently disagrees with the rest of the Jenny stack."),
    ("calibration", 70.0,    None,   "Its confidence has been reasonably calibrated to outcomes.",       "Its confidence has been poorly calibrated to outcomes."),
    ("entry",       65.0,    45.0,   "Its entry calls have lined up well with later trade outcomes.",    "Its entry calls have been too noisy versus realized outcomes."),
    ("risk",        70.0,    50.0,   "It has done a good job flagging when risk should matter more than conviction.", "It has been late to respect downside risk when trades weaken."),
    ("exit",        70.0,    50.0,   "Its exit and trim instincts have been timely enough to trust more.", "Its exit timing still needs work before it should drive sells."),
    ("alert",       65.0,    45.0,   "Its alerts have usually been selective instead of noisy.",         "It still throws too many confident alerts that do not age well."),
]


def _classify_score(
    value: float | None,
    good_threshold: float | None,
    bad_threshold: float | None,
    strength_msg: str,
    weakness_msg: str,
) -> tuple[str | None, str | None]:
    """Return (strength, weakness) label pair based on thresholds.

    good_threshold: value must be >= to earn a strength (None = never strong).
    bad_threshold: value must be < to earn a weakness (None = always weak if not strong).
    """
    if value is None:
        return None, None
    if good_threshold is not None and value >= good_threshold:
        return strength_msg, None
    if bad_threshold is None or value < bad_threshold:
        return None, weakness_msg
    return None, None


def summarize_scorecard(
    *,
    win_rate: float | None,
    avg_return: float | None,
    agreement_rate: float | None,
    calibration_score: float | None,
    entry_quality_score: float | None,
    risk_judgment_score: float | None,
    exit_timing_score: float | None,
    alert_discipline_score: float | None,
) -> tuple[list[str], list[str]]:
    values = [win_rate, avg_return, agreement_rate, calibration_score,
              entry_quality_score, risk_judgment_score, exit_timing_score, alert_discipline_score]
    strengths: list[str] = []
    weaknesses: list[str] = []
    for (_, good_at, bad_at, s_msg, w_msg), value in zip(_SCORE_RULES, values, strict=True):
        s, w = _classify_score(value, good_at, bad_at, s_msg, w_msg)
        if s:
            strengths.append(s)
        if w:
            weaknesses.append(w)

    if not strengths:
        strengths.append("Jenny is still gathering enough history to judge this agent fairly.")
    if not weaknesses:
        weaknesses.append("No persistent weakness stands out from the current sample.")

    return strengths[:3], weaknesses[:3]


def link_evaluations_to_reviews(
    evaluations: list[JennyAgentEvaluation],
    reviews_by_symbol: dict[str, list[JennyTradeReview]],
) -> list[tuple[JennyAgentEvaluation, JennyTradeReview]]:
    linked: list[tuple[JennyAgentEvaluation, JennyTradeReview]] = []
    for evaluation in evaluations:
        reviews = reviews_by_symbol.get(evaluation.symbol, [])
        if not reviews:
            continue
        evaluation_at = parse_timestamp(evaluation.created_at)
        sorted_reviews = sorted(reviews, key=lambda r: parse_timestamp(r.created_at))
        review = next(
            (r for r in sorted_reviews if parse_timestamp(r.created_at) >= evaluation_at),
            sorted_reviews[-1],
        )
        linked.append((evaluation, review))
    return linked


def score_entry_quality(
    linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
    positive_verdicts: set[str],
) -> float | None:
    scores: list[float] = []
    for evaluation, review in linked_pairs:
        return_pct = review.return_pct
        if return_pct is None:
            continue
        if return_pct == 0:
            scores.append(50.0)
            continue
        directional_positive = return_pct > 0
        verdict_positive = evaluation.verdict in positive_verdicts
        scores.append(100.0 if directional_positive == verdict_positive else 0.0)
    return sum(scores) / len(scores) if scores else None


def score_risk_judgment(
    linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
) -> float | None:
    risk_scores = {
        "buy": {True: 100.0, False: 0.0},
        "hold": {True: 85.0, False: 20.0},
        "review": {True: 55.0, False: 80.0},
        "trim": {True: 75.0, False: 90.0},
        "exit": {True: 45.0, False: 100.0},
        "avoid": {True: 20.0, False: 90.0},
    }
    scores = [
        risk_scores.get(e.verdict, {True: 50.0, False: 50.0})[(r.return_pct or 0.0) > 0]
        for e, r in linked_pairs
        if r.return_pct is not None
    ]
    return sum(scores) / len(scores) if scores else None


def score_exit_timing(
    agent_name: str,
    linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
) -> float | None:
    exit_scores = {
        "buy": {True: 100.0, False: 0.0},
        "hold": {True: 100.0, False: 20.0},
        "review": {True: 70.0, False: 80.0},
        "trim": {True: 95.0, False: 90.0},
        "exit": {True: 90.0, False: 100.0},
        "avoid": {True: 35.0, False: 85.0},
    }
    scores: list[float] = []
    for evaluation, review in linked_pairs:
        if review.return_pct is None:
            continue
        consensus_verdicts = review.agent_consensus.get("agent_verdicts", {})
        verdict = str(consensus_verdicts.get(agent_name, evaluation.verdict))
        scores.append(exit_scores.get(verdict, {True: 50.0, False: 50.0})[(review.return_pct or 0.0) > 0])
    return sum(scores) / len(scores) if scores else None


def score_alert_discipline(
    linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
    positive_verdicts: set[str],
) -> float | None:
    scores: list[float] = []
    for evaluation, review in linked_pairs:
        if review.return_pct is None:
            continue
        confidence = evaluation.confidence if evaluation.confidence is not None else 0.5
        directional_positive = (review.return_pct or 0.0) > 0
        verdict_positive = evaluation.verdict in positive_verdicts
        if directional_positive == verdict_positive:
            scores.append(100.0)
        else:
            scores.append(max(0.0, 75.0 - confidence * 100.0))
    return sum(scores) / len(scores) if scores else None


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
