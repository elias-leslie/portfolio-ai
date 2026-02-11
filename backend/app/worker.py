"""Hatchet worker entrypoint.

Registers all workflows and starts the worker process.
Run with: python -m app.worker
"""

from __future__ import annotations

from app.hatchet_app import hatchet
from app.workflows.agents import (
    run_discovery_agent_wf,
    run_portfolio_analyzer_wf,
    schedule_new_symbol_wf,
    update_paper_trades_wf,
)
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
from app.workflows.maintenance import (
    check_all_data_freshness_wf,
    check_data_source_health_wf,
    check_disk_space_wf,
    cleanup_debug_captures_wf,
    cleanup_news_wf,
    cleanup_old_agent_runs_wf,
    cleanup_old_backups_wf,
    cleanup_old_logs_wf,
    cleanup_old_models_wf,
    cleanup_old_versions_wf,
    cleanup_orphaned_wf,
    cleanup_solution_state_wf,
    cleanup_temp_wf,
    db_size_wf,
    maintain_data_freshness_wf,
    profile_news_wf,
    reset_source_metrics_wf,
    vacuum_db_wf,
)
from app.workflows.monitoring import (
    generate_sitemap_wf,
    monitor_theses_wf,
    qa_scan_wf,
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
from app.workflows.strategy import (
    auto_paper_trade_wf,
    auto_promote_wf,
    covariance_wf,
    daily_signals_wf,
    daily_strategy_refresh_wf,
    eval_strategy_wf,
    generate_signal_wf,
    portfolio_snapshots_wf,
    rules_validation_wf,
    strategy_metrics_wf,
    trigger_from_seed_wf,
    trigger_top_strategies_wf,
    weekly_evolution_wf,
    weekly_optimization_wf,
    weekly_strategy_gen_wf,
)
from app.workflows.watchlist import (
    discover_candidates_wf,
    refresh_news_sentiment_wf,
    refresh_single_symbol_wf,
    refresh_watchlist_scores_wf,
    trim_underperforming_wf,
)


def main() -> None:
    worker = hatchet.worker(
        "portfolio-worker",
        workflows=[
            # Maintenance (18)
            vacuum_db_wf,
            cleanup_news_wf,
            cleanup_old_agent_runs_wf,
            cleanup_orphaned_wf,
            cleanup_old_backups_wf,
            cleanup_old_models_wf,
            cleanup_solution_state_wf,
            db_size_wf,
            cleanup_old_logs_wf,
            cleanup_temp_wf,
            check_disk_space_wf,
            maintain_data_freshness_wf,
            check_all_data_freshness_wf,
            check_data_source_health_wf,
            cleanup_debug_captures_wf,
            cleanup_old_versions_wf,
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
            # Strategy (15)
            eval_strategy_wf,
            auto_promote_wf,
            daily_strategy_refresh_wf,
            weekly_strategy_gen_wf,
            weekly_evolution_wf,
            daily_signals_wf,
            auto_paper_trade_wf,
            portfolio_snapshots_wf,
            covariance_wf,
            rules_validation_wf,
            weekly_optimization_wf,
            trigger_from_seed_wf,
            trigger_top_strategies_wf,
            generate_signal_wf,
            strategy_metrics_wf,
            # Watchlist (5)
            refresh_watchlist_scores_wf,
            refresh_single_symbol_wf,
            refresh_news_sentiment_wf,
            discover_candidates_wf,
            trim_underperforming_wf,
            # Agents (4)
            run_discovery_agent_wf,
            run_portfolio_analyzer_wf,
            update_paper_trades_wf,
            schedule_new_symbol_wf,
            # Monitoring (3)
            qa_scan_wf,
            generate_sitemap_wf,
            monitor_theses_wf,
            # Events (1)
            cross_validate_insight_wf,
        ],
    )
    worker.start()


if __name__ == "__main__":
    main()
