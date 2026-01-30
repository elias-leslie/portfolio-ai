"""Strategy evaluation metrics collection tasks.

Daily/weekly/monthly aggregation of strategy performance for drift monitoring.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from ..celery_app import celery_app
from ..logging_config import get_logger
from ..storage import get_storage

if TYPE_CHECKING:
    from typing import Any

    from ..storage.facade import PortfolioStorage

logger = get_logger(__name__)


def _get_signal_metrics(
    storage: PortfolioStorage, date_str: str
) -> tuple[dict[str, Any], dict[str, Any], float]:
    """Fetch signal counts and score stats from watchlist snapshots."""
    df = storage.query(
        "SELECT signal_type, COUNT(*) as count, AVG(overall_score) as avg_overall, "
        "AVG(technical_score) as avg_technical, AVG(fundamental_score) as avg_fundamental, "
        "STDDEV(overall_score) as score_stdev FROM watchlist_snapshots_v "
        "WHERE DATE(fetched_at) = ? GROUP BY signal_type",
        [date_str],
    )
    signal_counts: dict[str, Any] = {"BUY": 0, "HOLD": 0, "AVOID": 0}
    avg_scores: dict[str, Any] = {"overall": 0.0, "technical": 0.0, "fundamental": 0.0}
    score_stdev = 0.0
    if not df.is_empty():
        for row in df.to_dicts():
            signal_counts[row.get("signal_type", "HOLD")] = int(row.get("count", 0))
            avg_scores = {
                "overall": float(row.get("avg_overall", 0)),
                "technical": float(row.get("avg_technical", 0)),
                "fundamental": float(row.get("avg_fundamental", 0)),
            }
            score_stdev = float(row.get("score_stdev", 0))
    return signal_counts, avg_scores, score_stdev


def _get_trades_metrics(storage: PortfolioStorage, date_str: str) -> tuple[dict[str, Any], float]:
    """Fetch trade outcomes and calculate win rate."""
    df = storage.query(
        "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'closed_win' THEN 1 ELSE 0 END) as wins, "
        "SUM(CASE WHEN status = 'closed_loss' THEN 1 ELSE 0 END) as losses, AVG(return_pct) as avg_return, "
        "MAX(return_pct) as best_return, MIN(return_pct) as worst_return FROM idea_outcomes "
        "WHERE DATE(exit_date) = ? AND status IN ('closed_win', 'closed_loss', 'stopped_out')",
        [date_str],
    )
    stats: dict[str, Any] = {
        "total": 0,
        "wins": 0,
        "losses": 0,
        "avg_return": 0.0,
        "best": 0.0,
        "worst": 0.0,
    }
    win_rate = 0.0
    if not df.is_empty():
        row = df.to_dicts()[0]
        stats = {
            "total": int(row.get("total", 0)),
            "wins": int(row.get("wins", 0)),
            "losses": int(row.get("losses", 0)),
            "avg_return": float(row.get("avg_return", 0)),
            "best": float(row.get("best_return", 0)),
            "worst": float(row.get("worst_return", 0)),
        }
        total = int(stats["total"])
        wins = int(stats["wins"])
        win_rate = (wins / total) * 100.0 if total > 0 else 0.0
    return stats, win_rate


def _get_review_metrics(
    storage: PortfolioStorage, date_str: str
) -> tuple[dict[str, Any], float, float]:
    """Fetch strategy review disagreement stats."""
    df = storage.query(
        "SELECT COUNT(*) as total, SUM(CASE WHEN disagreement = true THEN 1 ELSE 0 END) as disagreements, "
        "SUM(CASE WHEN provider_disagreement = true THEN 1 ELSE 0 END) as provider_disagreements, "
        "SUM(CASE WHEN disagreement_severity = 'major' THEN 1 ELSE 0 END) as major_disagreements, "
        "SUM(CASE WHEN disagreement_severity = 'minor' THEN 1 ELSE 0 END) as minor_disagreements, "
        "AVG(agreement_score) as avg_agreement FROM strategy_reviews WHERE DATE(created_at) = ?",
        [date_str],
    )
    stats: dict[str, Any] = {
        "total": 0,
        "disagreements": 0,
        "provider_disagreements": 0,
        "major_disagreements": 0,
        "minor_disagreements": 0,
        "avg_agreement": 0.0,
    }
    disagreement_rate = 0.0
    provider_disagreement_rate = 0.0
    if not df.is_empty():
        row = df.to_dicts()[0]
        stats = {
            k: float(row.get(k, 0) or 0) if k == "avg_agreement" else int(row.get(k, 0) or 0)
            for k in stats
        }
        total = int(stats["total"])
        if total > 0:
            disagreement_rate = (float(stats["disagreements"]) / total) * 100.0
            provider_disagreement_rate = (float(stats["provider_disagreements"]) / total) * 100.0
    return stats, disagreement_rate, provider_disagreement_rate


def _get_cumulative_return(storage: PortfolioStorage, date_str: str) -> float:
    """Calculate cumulative return from all closed trades to date."""
    df = storage.query(
        "SELECT SUM(return_pct) as cumulative FROM idea_outcomes "
        "WHERE status IN ('closed_win', 'closed_loss', 'stopped_out') AND exit_date <= ?",
        [date_str],
    )
    return df.to_dicts()[0].get("cumulative", 0) if not df.is_empty() else 0


def _insert_metrics(
    storage: PortfolioStorage,
    date_str: str,
    signal_counts: dict[str, Any],
    avg_scores: dict[str, Any],
    score_stdev: float,
    trades_stats: dict[str, Any],
    win_rate: float,
    reviews_stats: dict[str, Any],
    disagreement_rate: float,
    provider_disagreement_rate: float,
    cumulative_return: float,
) -> None:
    """Insert aggregated metrics into strategy_metrics table."""
    with storage.connection() as conn:
        conn.execute(
            "INSERT INTO strategy_metrics (id, metric_date, metric_type, total_signals, buy_signals, "
            "hold_signals, avoid_signals, signals_traded, winning_trades, losing_trades, win_rate_pct, "
            "avg_return_pct, best_return_pct, worst_return_pct, cumulative_return_pct, avg_overall_score, "
            "avg_technical_score, avg_fundamental_score, score_stdev, reviews_count, disagreements_count, "
            "disagreement_rate_pct, provider_disagreements_count, provider_disagreement_rate_pct, "
            "avg_agreement_score, major_disagreements_count, minor_disagreements_count, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                str(uuid.uuid4()),
                date_str,
                "daily",
                sum(signal_counts.values()),
                signal_counts["BUY"],
                signal_counts["HOLD"],
                signal_counts["AVOID"],
                trades_stats["total"],
                trades_stats["wins"],
                trades_stats["losses"],
                win_rate,
                trades_stats["avg_return"],
                trades_stats["best"],
                trades_stats["worst"],
                cumulative_return,
                avg_scores["overall"],
                avg_scores["technical"],
                avg_scores["fundamental"],
                score_stdev,
                reviews_stats["total"],
                reviews_stats["disagreements"],
                disagreement_rate,
                reviews_stats["provider_disagreements"],
                provider_disagreement_rate,
                reviews_stats["avg_agreement"],
                reviews_stats["major_disagreements"],
                reviews_stats["minor_disagreements"],
                datetime.now(UTC),
            ],
        )
        conn.commit()


@celery_app.task(name="strategy_metrics.daily_collection")
def collect_daily_strategy_metrics() -> dict[str, object]:
    """Collect strategy performance metrics for the previous day."""
    storage = get_storage()
    yesterday = str((datetime.now(UTC) - timedelta(days=1)).date())
    logger.info(f"Collecting strategy metrics for {yesterday}")
    try:
        signal_counts, avg_scores, score_stdev = _get_signal_metrics(storage, yesterday)
        trades_stats, win_rate = _get_trades_metrics(storage, yesterday)
        reviews_stats, disagreement_rate, provider_disagreement_rate = _get_review_metrics(
            storage, yesterday
        )
        cumulative_return = _get_cumulative_return(storage, yesterday)
        _insert_metrics(
            storage,
            yesterday,
            signal_counts,
            avg_scores,
            score_stdev,
            trades_stats,
            win_rate,
            reviews_stats,
            disagreement_rate,
            provider_disagreement_rate,
            cumulative_return,
        )
        logger.info(
            f"Strategy metrics collected for {yesterday}",
            extra={
                "date": yesterday,
                "signals": sum(signal_counts.values()),
                "win_rate": win_rate,
                "disagreement_rate": disagreement_rate,
                "provider_disagreement_rate": provider_disagreement_rate,
            },
        )
        return {
            "status": "success",
            "date": yesterday,
            "metrics": {
                "signals": signal_counts,
                "trades": trades_stats,
                "reviews": reviews_stats,
                "win_rate_pct": win_rate,
                "disagreement_rate_pct": disagreement_rate,
                "provider_disagreement_rate_pct": provider_disagreement_rate,
                "avg_agreement_score": reviews_stats["avg_agreement"],
            },
        }
    except Exception as e:
        logger.error(f"Failed to collect strategy metrics: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
