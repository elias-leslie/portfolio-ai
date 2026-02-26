"""Private helpers for rules_validation_tasks.

SQL constants and shared type aliases - not part of the public task API.
"""

from __future__ import annotations

PerformanceData = dict[str, object]

_SQL_INSERT_REPORT = (
    "INSERT INTO rules_validation_reports (rules_version, validation_time, overall_status, "
    "critical_count, warning_count, info_count, validation_errors, recommendations, summary) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
_SQL_INSERT_ALERT = (
    "INSERT INTO maintenance_log (task_name, status, message) VALUES (%s, %s, %s)"
)
_SQL_UPDATE_RECS = (
    "UPDATE rules_validation_reports SET recommendations = %s, performance_data = %s "
    "WHERE id = (SELECT id FROM rules_validation_reports ORDER BY validation_time DESC LIMIT 1)"
)
_SQL_TRADE_STATS = (
    "SELECT COUNT(*) as total_trades, "
    "SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END)::float / COUNT(*) as win_rate, "
    "AVG(profit_loss) as avg_pnl, STDDEV(profit_loss) as std_pnl, "
    "MAX(drawdown_from_peak) as max_drawdown FROM paper_trade_transactions "
    "WHERE created_at >= NOW() - INTERVAL '30 days' AND status = 'closed'"
)
_SQL_SIGNAL_STATS = (
    "SELECT signal_classification, COUNT(*) as signal_count, AVG(overall_score) as avg_score "
    "FROM watchlist_snapshots_core "
    "WHERE snapshot_time >= NOW() - INTERVAL '30 days' AND signal_classification IS NOT NULL "
    "GROUP BY signal_classification ORDER BY signal_classification"
)
