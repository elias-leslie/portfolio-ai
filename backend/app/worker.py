"""Hatchet worker entrypoint.

Registers all workflows and starts the worker process.
Run with: python -m app.worker
"""

from __future__ import annotations

import os

from app.hatchet_app import hatchet
from app.logging_config import configure_logging
from app.workflows.agents import schedule_new_symbol_wf
from app.workflows.catalysts import portfolio_catalyst_prewarm_wf
from app.workflows.committee_fanout import committee_fanout_wf
from app.workflows.data_refresh import (
    backfill_indicators_wf,
    calculate_fear_greed_wf,
    fetch_options_activity_wf,
    fetch_putcall_ratio_wf,
    ingest_fundamental_data_wf,
    ingest_macro_indicators_wf,
    ingest_ohlcv_wf,
    maintain_historical_wf,
    populate_fear_greed_inputs_wf,
    refresh_daily_ohlcv_wf,
    refresh_watchlist_ohlcv_wf,
    update_technical_indicators_wf,
)
from app.workflows.events import cross_validate_insight_wf
from app.workflows.ips_drift import portfolio_drift_snapshot_wf
from app.workflows.jenny import (
    jenny_daily_household_maintenance_wf,
    jenny_daily_operator_wf,
    jenny_weekly_learning_wf,
)
from app.workflows.macro_calendar import market_macro_calendar_ingestion_wf
from app.workflows.macro_gate import macro_gate_wf
from app.workflows.maintenance import (
    check_all_data_freshness_wf,
    check_data_source_health_wf,
    check_disk_space_wf,
    cleanup_debug_captures_wf,
    cleanup_maintenance_wf,
    cleanup_news_wf,
    cleanup_old_agent_runs_wf,
    cleanup_old_backups_wf,
    cleanup_old_logs_wf,
    cleanup_old_models_wf,
    cleanup_orphaned_wf,
    cleanup_snapshots_wf,
    cleanup_temp_wf,
    db_size_wf,
    maintain_data_freshness_wf,
    profile_news_wf,
    reset_source_metrics_wf,
    rotate_logs_wf,
    vacuum_db_wf,
)
from app.workflows.reference import (
    corporate_actions_wf,
    earnings_surprises_wf,
    financial_health_wf,
    refresh_analyst_revisions_wf,
    refresh_risk_metrics_wf,
    refresh_sec_cik_wf,
    retrain_ml_wf,
    valuation_metrics_wf,
    yfinance_ref_wf,
)
from app.workflows.research_universe import research_universe_refresh_wf
from app.workflows.scanner import scanner_wf
from app.workflows.strategy import (
    covariance_wf,
    portfolio_snapshots_wf,
    rules_validation_wf,
    weekly_optimization_wf,
)
from app.workflows.tlh import portfolio_tlh_scan_wf
from app.workflows.watchlist import (
    discover_candidates_wf,
    refresh_news_sentiment_wf,
    refresh_single_symbol_wf,
    refresh_watchlist_scores_wf,
    trim_underperforming_wf,
)


def main() -> None:
    configure_logging()
    worker = hatchet.worker(
        "portfolio-worker",
        workflows=[
            # Maintenance
            rotate_logs_wf,
            vacuum_db_wf,
            cleanup_news_wf,
            cleanup_old_agent_runs_wf,
            cleanup_orphaned_wf,
            cleanup_snapshots_wf,
            cleanup_maintenance_wf,
            cleanup_old_backups_wf,
            cleanup_old_models_wf,
            db_size_wf,
            cleanup_old_logs_wf,
            cleanup_temp_wf,
            check_disk_space_wf,
            maintain_data_freshness_wf,
            check_all_data_freshness_wf,
            check_data_source_health_wf,
            cleanup_debug_captures_wf,
            reset_source_metrics_wf,
            profile_news_wf,
            # Data Refresh (12)
            refresh_daily_ohlcv_wf,
            refresh_watchlist_ohlcv_wf,
            backfill_indicators_wf,
            populate_fear_greed_inputs_wf,
            calculate_fear_greed_wf,
            maintain_historical_wf,
            fetch_options_activity_wf,
            fetch_putcall_ratio_wf,
            ingest_ohlcv_wf,
            update_technical_indicators_wf,
            ingest_fundamental_data_wf,
            ingest_macro_indicators_wf,
            # Reference (9)
            yfinance_ref_wf,
            valuation_metrics_wf,
            refresh_analyst_revisions_wf,
            earnings_surprises_wf,
            financial_health_wf,
            refresh_risk_metrics_wf,
            corporate_actions_wf,
            refresh_sec_cik_wf,
            retrain_ml_wf,
            # Portfolio maintenance (4)
            portfolio_snapshots_wf,
            covariance_wf,
            rules_validation_wf,
            weekly_optimization_wf,
            # Watchlist (5)
            refresh_watchlist_scores_wf,
            refresh_single_symbol_wf,
            refresh_news_sentiment_wf,
            discover_candidates_wf,
            trim_underperforming_wf,
            # Agents (1)
            schedule_new_symbol_wf,
            # Jenny (3)
            jenny_daily_operator_wf,
            jenny_weekly_learning_wf,
            jenny_daily_household_maintenance_wf,
            # Macro calendar ingestion
            market_macro_calendar_ingestion_wf,
            # Signal stack: L1 macro gate -> L2 scanner -> L3 committee fan-out;
            # universe refresh feeds all three.
            research_universe_refresh_wf,
            macro_gate_wf,
            scanner_wf,
            committee_fanout_wf,
            # Events (1)
            cross_validate_insight_wf,
            # Portfolio TLH (1)
            portfolio_tlh_scan_wf,
            # Portfolio IPS drift (1)
            portfolio_drift_snapshot_wf,
            # Portfolio catalyst calendar (1)
            portfolio_catalyst_prewarm_wf,
        ],
    )
    worker.handle_kill = False
    worker.start()
    os._exit(0)


if __name__ == "__main__":
    main()
