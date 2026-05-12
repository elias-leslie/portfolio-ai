from app.workflows.data_refresh_schedules import (
    DAILY_OHLCV_CRONS,
    FEAR_GREED_CALC_CRONS,
    FEAR_GREED_INPUTS_CRONS,
    FUNDAMENTAL_INGESTION_CRONS,
    HISTORICAL_OHLCV_MAINTENANCE_CRONS,
    MACRO_INDICATOR_INGESTION_CRONS,
    OPTIONS_ACTIVITY_CRONS,
    PUTCALL_RATIO_CRONS,
    TECHNICAL_INDICATOR_BACKFILL_CRONS,
    WATCHLIST_OHLCV_CRONS,
)


def test_fear_greed_schedules_restore_intraday_and_after_close_refreshes() -> None:
    assert FEAR_GREED_INPUTS_CRONS == [
        "45 2 * * *",
        "15 15 * * *",
        "15 17 * * *",
        "47 21 * * *",
    ]
    assert FEAR_GREED_CALC_CRONS == [
        "2 3 * * *",
        "30 15 * * *",
        "30 17 * * *",
        "0 22 * * *",
    ]


def test_putcall_ratio_schedule_covers_market_open_and_close() -> None:
    assert PUTCALL_RATIO_CRONS == [
        "30 14 * * *",
        "39 21 * * *",
    ]


def test_core_ingestion_schedules_are_centralized() -> None:
    assert DAILY_OHLCV_CRONS == ["0 2 * * *"]
    assert WATCHLIST_OHLCV_CRONS == ["15 2 * * *"]
    assert TECHNICAL_INDICATOR_BACKFILL_CRONS == ["30 2 * * *"]
    assert HISTORICAL_OHLCV_MAINTENANCE_CRONS == ["15 4 * * *"]
    assert OPTIONS_ACTIVITY_CRONS == ["15 21 * * *"]
    assert FUNDAMENTAL_INGESTION_CRONS == ["10 6 * * 0"]
    assert MACRO_INDICATOR_INGESTION_CRONS == ["30 6 * * *"]
