"""Strategy evaluation metrics collection tasks.

Daily/weekly/monthly aggregation of strategy performance for drift monitoring.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from ..celery_app import celery_app
from ..logging_config import get_logger
from ..storage import get_storage

logger = get_logger(__name__)


@celery_app.task(name="strategy_metrics.daily_collection")
def collect_daily_strategy_metrics() -> dict[str, object]:
    """Collect strategy performance metrics for the previous day.

    Aggregates:
    - Signal counts (BUY/HOLD/AVOID)
    - Win rates from paper trades
    - Return metrics
    - Score distributions (for drift detection)
    - LLM reviewer disagreement rates

    Returns:
        Dict with collection stats
    """
    storage = get_storage()
    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()

    logger.info(f"Collecting strategy metrics for {yesterday}")

    try:
        # 1. Signal counts from watchlist snapshots (using normalized view)
        signals_df = storage.query(
            """
            SELECT
                signal_type,
                COUNT(*) as count,
                AVG(overall_score) as avg_overall,
                AVG(technical_score) as avg_technical,
                AVG(fundamental_score) as avg_fundamental,
                STDDEV(overall_score) as score_stdev
            FROM watchlist_snapshots_v
            WHERE DATE(fetched_at) = ?
            GROUP BY signal_type
            """,
            [str(yesterday)],
        )

        signal_counts = {"BUY": 0, "HOLD": 0, "AVOID": 0}
        avg_scores = {"overall": 0, "technical": 0, "fundamental": 0}
        score_stdev = 0

        if not signals_df.is_empty():
            for row in signals_df.to_dicts():
                signal_type = row.get("signal_type", "HOLD")
                signal_counts[signal_type] = row.get("count", 0)
                avg_scores["overall"] = row.get("avg_overall", 0)
                avg_scores["technical"] = row.get("avg_technical", 0)
                avg_scores["fundamental"] = row.get("avg_fundamental", 0)
                score_stdev = row.get("score_stdev", 0)

        # 2. Win rate from closed paper trades
        trades_df = storage.query(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'closed_win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status = 'closed_loss' THEN 1 ELSE 0 END) as losses,
                AVG(return_pct) as avg_return,
                MAX(return_pct) as best_return,
                MIN(return_pct) as worst_return
            FROM idea_outcomes
            WHERE DATE(exit_date) = ?
            AND status IN ('closed_win', 'closed_loss', 'stopped_out')
            """,
            [str(yesterday)],
        )

        trades_stats = {"total": 0, "wins": 0, "losses": 0, "avg_return": 0, "best": 0, "worst": 0}
        if not trades_df.is_empty():
            row = trades_df.to_dicts()[0]
            trades_stats = {
                "total": row.get("total", 0),
                "wins": row.get("wins", 0),
                "losses": row.get("losses", 0),
                "avg_return": row.get("avg_return", 0),
                "best": row.get("best_return", 0),
                "worst": row.get("worst_return", 0),
            }

        win_rate = (
            (trades_stats["wins"] / trades_stats["total"]) * 100 if trades_stats["total"] > 0 else 0
        )

        # 3. LLM reviewer disagreement rate (rules vs LLM + provider vs provider)
        reviews_df = storage.query(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN disagreement = true THEN 1 ELSE 0 END) as disagreements,
                SUM(CASE WHEN provider_disagreement = true THEN 1 ELSE 0 END) as provider_disagreements,
                SUM(CASE WHEN disagreement_severity = 'major' THEN 1 ELSE 0 END) as major_disagreements,
                SUM(CASE WHEN disagreement_severity = 'minor' THEN 1 ELSE 0 END) as minor_disagreements,
                AVG(agreement_score) as avg_agreement
            FROM strategy_reviews
            WHERE DATE(created_at) = ?
            """,
            [str(yesterday)],
        )

        reviews_stats = {
            "total": 0,
            "disagreements": 0,
            "provider_disagreements": 0,
            "major_disagreements": 0,
            "minor_disagreements": 0,
            "avg_agreement": 0,
        }
        if not reviews_df.is_empty():
            row = reviews_df.to_dicts()[0]
            reviews_stats = {
                "total": row.get("total", 0) or 0,
                "disagreements": row.get("disagreements", 0) or 0,
                "provider_disagreements": row.get("provider_disagreements", 0) or 0,
                "major_disagreements": row.get("major_disagreements", 0) or 0,
                "minor_disagreements": row.get("minor_disagreements", 0) or 0,
                "avg_agreement": row.get("avg_agreement", 0) or 0,
            }

        disagreement_rate = (
            (reviews_stats["disagreements"] / reviews_stats["total"]) * 100
            if reviews_stats["total"] > 0
            else 0
        )

        provider_disagreement_rate = (
            (reviews_stats["provider_disagreements"] / reviews_stats["total"]) * 100
            if reviews_stats["total"] > 0
            else 0
        )

        # 4. Calculate cumulative return (sum of all closed trades to date)
        cumulative_df = storage.query(
            """
            SELECT SUM(return_pct) as cumulative
            FROM idea_outcomes
            WHERE status IN ('closed_win', 'closed_loss', 'stopped_out')
            AND exit_date <= ?
            """,
            [str(yesterday)],
        )

        cumulative_return = 0
        if not cumulative_df.is_empty():
            cumulative_return = cumulative_df.to_dicts()[0].get("cumulative", 0)

        # 5. Insert metrics record
        metric_id = str(uuid.uuid4())
        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO strategy_metrics (
                    id, metric_date, metric_type,
                    total_signals, buy_signals, hold_signals, avoid_signals,
                    signals_traded, winning_trades, losing_trades, win_rate_pct,
                    avg_return_pct, best_return_pct, worst_return_pct, cumulative_return_pct,
                    avg_overall_score, avg_technical_score, avg_fundamental_score, score_stdev,
                    reviews_count, disagreements_count, disagreement_rate_pct,
                    provider_disagreements_count, provider_disagreement_rate_pct,
                    avg_agreement_score, major_disagreements_count, minor_disagreements_count,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    metric_id,
                    str(yesterday),
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

        logger.info(
            f"Strategy metrics collected for {yesterday}",
            extra={
                "date": str(yesterday),
                "signals": sum(signal_counts.values()),
                "win_rate": win_rate,
                "disagreement_rate": disagreement_rate,
                "provider_disagreement_rate": provider_disagreement_rate,
            },
        )

        return {
            "status": "success",
            "date": str(yesterday),
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
