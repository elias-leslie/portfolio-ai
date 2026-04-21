from app.workflows.data_refresh_schedules import (
    FEAR_GREED_CALC_CRONS,
    FEAR_GREED_INPUTS_CRONS,
    MARKET_PREDICTION_AFTER_CLOSE_CRONS,
    MARKET_PREDICTION_MORNING_CRONS,
    MARKET_PREDICTION_SUNDAY_CRONS,
    PUTCALL_RATIO_CRONS,
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


def test_market_prediction_schedules_cover_morning_after_close_and_sunday_prep() -> None:
    assert MARKET_PREDICTION_MORNING_CRONS == ["15 13 * * 1-5"]
    assert MARKET_PREDICTION_AFTER_CLOSE_CRONS == ["10 22 * * 1-5"]
    assert MARKET_PREDICTION_SUNDAY_CRONS == ["0 22 * * 0"]
