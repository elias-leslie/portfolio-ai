import datetime as dt

from app.sources import polygon_source


def test_iterate_dates_uses_completed_trading_days(monkeypatch) -> None:
    monkeypatch.setattr(polygon_source, "get_expected_data_date", lambda: dt.date(2026, 6, 29))

    assert polygon_source._iterate_dates(dt.date(2026, 6, 26), dt.date(2026, 6, 30)) == [
        "2026-06-26",
        "2026-06-29",
    ]
