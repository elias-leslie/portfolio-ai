from app.workflows.data_refresh_schedules import (
    FEAR_GREED_CALC_CRONS,
    FEAR_GREED_INPUTS_CRONS,
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
