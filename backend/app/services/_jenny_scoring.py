"""Pure helpers for Jenny scorecards and aggregate reviews."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.models.jenny import (
    JennyAgentEvaluation,
    JennyAgentScorecard,
    JennySymbolReview,
    JennyTradeReview,
)
from app.models.thesis import Thesis


def aggregate_symbol_review(
    *,
    symbol: str,
    evaluations: list[dict[str, Any]] | list[JennyAgentEvaluation],
    thesis: Thesis | None,
    final_verdict_priority: dict[str, int],
    now_iso: str,
) -> JennySymbolReview:
    normalized: list[JennyAgentEvaluation] = []
    for evaluation in evaluations:
        if isinstance(evaluation, JennyAgentEvaluation):
            normalized.append(evaluation)
            continue
        normalized.append(
            JennyAgentEvaluation(
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
        )

    verdict_counts = Counter(evaluation.verdict for evaluation in normalized)
    final_verdict = (
        sorted(
            verdict_counts,
            key=lambda verdict: (verdict_counts[verdict], final_verdict_priority.get(verdict, 0)),
            reverse=True,
        )[0]
        if verdict_counts
        else "review"
    )
    confidences = [evaluation.confidence for evaluation in normalized if evaluation.confidence is not None]
    reasons = [evaluation.rationale for evaluation in normalized[:3]]

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
    positive_verdict_count = sum(1 for evaluation in evaluations if evaluation.verdict in positive_verdicts)
    linked_pairs = link_evaluations_to_reviews(evaluations, reviews_by_symbol)
    unique_reviews = {review.id: review for _, review in linked_pairs}.values()
    completed_reviews = len(unique_reviews)
    positive_reviews = [review for review in unique_reviews if (review.return_pct or 0.0) > 0]
    avg_return = (
        sum((review.return_pct or 0.0) for review in unique_reviews) / completed_reviews
        if completed_reviews
        else None
    )
    win_rate = len(positive_reviews) / completed_reviews if completed_reviews else None

    grouped_by_symbol: dict[str, list[JennyAgentEvaluation]] = defaultdict(list)
    for evaluation in evaluations:
        grouped_by_symbol[evaluation.symbol].append(evaluation)
    agreement_hits = 0
    calibration_scores: list[float] = []
    for symbol_evaluations in grouped_by_symbol.values():
        counts = Counter(evaluation.verdict for evaluation in symbol_evaluations)
        final_verdict = sorted(
            counts,
            key=lambda verdict: (counts[verdict], final_verdict_priority.get(verdict, 0)),
            reverse=True,
        )[0]
        for evaluation in symbol_evaluations:
            if evaluation.verdict == final_verdict:
                agreement_hits += 1
            linked_review = next(
                (review for candidate, review in linked_pairs if candidate.id == evaluation.id),
                None,
            )
            if linked_review and evaluation.confidence is not None:
                realized = 100.0 if (linked_review.return_pct or 0.0) > 0 else 0.0
                calibration_scores.append(max(0.0, 100.0 - abs(evaluation.confidence * 100.0 - realized)))

    agreement_rate = agreement_hits / total_evaluations if total_evaluations else None
    calibration_score = (
        sum(calibration_scores) / len(calibration_scores) if calibration_scores else None
    )
    entry_quality_score = score_entry_quality(linked_pairs, positive_verdicts)
    risk_judgment_score = score_risk_judgment(linked_pairs)
    exit_timing_score = score_exit_timing(agent_name, linked_pairs)
    alert_discipline_score = score_alert_discipline(linked_pairs, positive_verdicts)
    strengths, weaknesses = summarize_scorecard(
        win_rate=win_rate,
        avg_return=avg_return,
        agreement_rate=agreement_rate,
        calibration_score=calibration_score,
        entry_quality_score=entry_quality_score,
        risk_judgment_score=risk_judgment_score,
        exit_timing_score=exit_timing_score,
        alert_discipline_score=alert_discipline_score,
    )

    last_evaluation_at = max((evaluation.created_at for evaluation in evaluations), default=None)
    return JennyAgentScorecard(
        agent_name=agent_name,
        total_evaluations=total_evaluations,
        completed_reviews=completed_reviews,
        positive_verdicts=positive_verdict_count,
        win_rate=win_rate,
        avg_return_pct=avg_return,
        agreement_rate=agreement_rate,
        calibration_score=calibration_score,
        entry_quality_score=entry_quality_score,
        risk_judgment_score=risk_judgment_score,
        exit_timing_score=exit_timing_score,
        alert_discipline_score=alert_discipline_score,
        strengths=strengths,
        weaknesses=weaknesses,
        last_evaluation_at=last_evaluation_at,
        updated_at=now_iso,
    )


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
    strengths: list[str] = []
    weaknesses: list[str] = []

    if win_rate is not None and win_rate >= 0.55:
        strengths.append("Its reviewed symbols have produced more winners than losers.")
    elif win_rate is not None:
        weaknesses.append("Its reviewed symbols have not cleared a strong win rate yet.")

    if avg_return is not None and avg_return > 5:
        strengths.append("The average reviewed outcome has produced meaningful upside.")
    elif avg_return is not None and avg_return < 0:
        weaknesses.append("Average reviewed outcomes are still negative.")

    if agreement_rate is not None and agreement_rate >= 0.6:
        strengths.append("It usually aligns with the final multi-agent verdict.")
    elif agreement_rate is not None:
        weaknesses.append("It frequently disagrees with the rest of the Jenny stack.")

    if calibration_score is not None and calibration_score >= 70:
        strengths.append("Its confidence has been reasonably calibrated to outcomes.")
    elif calibration_score is not None:
        weaknesses.append("Its confidence has been poorly calibrated to outcomes.")

    if entry_quality_score is not None and entry_quality_score >= 65:
        strengths.append("Its entry calls have lined up well with later trade outcomes.")
    elif entry_quality_score is not None and entry_quality_score < 45:
        weaknesses.append("Its entry calls have been too noisy versus realized outcomes.")

    if risk_judgment_score is not None and risk_judgment_score >= 70:
        strengths.append("It has done a good job flagging when risk should matter more than conviction.")
    elif risk_judgment_score is not None and risk_judgment_score < 50:
        weaknesses.append("It has been late to respect downside risk when trades weaken.")

    if exit_timing_score is not None and exit_timing_score >= 70:
        strengths.append("Its exit and trim instincts have been timely enough to trust more.")
    elif exit_timing_score is not None and exit_timing_score < 50:
        weaknesses.append("Its exit timing still needs work before it should drive sells.")

    if alert_discipline_score is not None and alert_discipline_score >= 65:
        strengths.append("Its alerts have usually been selective instead of noisy.")
    elif alert_discipline_score is not None and alert_discipline_score < 45:
        weaknesses.append("It still throws too many confident alerts that do not age well.")

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
        sorted_reviews = sorted(reviews, key=lambda review: parse_timestamp(review.created_at))
        review = next(
            (
                candidate
                for candidate in sorted_reviews
                if parse_timestamp(candidate.created_at) >= evaluation_at
            ),
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
        risk_scores.get(evaluation.verdict, {True: 50.0, False: 50.0})[(review.return_pct or 0.0) > 0]
        for evaluation, review in linked_pairs
        if review.return_pct is not None
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

