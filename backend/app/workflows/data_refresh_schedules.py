"""Canonical cron schedules for data refresh workflows.

These lists preserve the pre-Hatchet refresh cadence so market sentiment data
stays current throughout the trading day and after the close.
"""

PUTCALL_RATIO_CRONS = [
    "30 14 * * *",
    "39 21 * * *",
]

FEAR_GREED_INPUTS_CRONS = [
    "45 2 * * *",
    "15 15 * * *",
    "15 17 * * *",
    "47 21 * * *",
]

FEAR_GREED_CALC_CRONS = [
    "2 3 * * *",
    "30 15 * * *",
    "30 17 * * *",
    "0 22 * * *",
]

DAILY_OHLCV_CRONS = ["0 2 * * *"]
WATCHLIST_OHLCV_CRONS = ["15 2 * * *"]
# Current-session intraday bars for the Investing > Symbols "Today" trendline.
# Hourly during the regular session, weekdays — the deliberately slow background
# baseline for when the PWA is closed ("hours, not minutes"). When the PWA is
# open, the Data Feed freshness path tops this up faster: intraday_bars is
# registered in TABLE_FRESHNESS_CONFIG, so the open-UI refresh remediates it the
# moment it ages past expected (bounded by the 30-min remediation cooldown). The
# 13-21 UTC window spans 9:30am-4pm ET under both EST and EDT; the
# yfinance/TwelveData/Polygon chain (intraday_ingestion) returns regular-hours
# bars, so off-session ticks are cheap no-ops re-pulling the latest session.
WATCHLIST_INTRADAY_CRONS = ["0 13-21 * * 1-5"]
HISTORICAL_OHLCV_MAINTENANCE_CRONS = ["15 4 * * *"]
TECHNICAL_INDICATOR_BACKFILL_CRONS = ["30 2 * * *"]
FUNDAMENTAL_INGESTION_CRONS = ["10 6 * * 0"]
MACRO_INDICATOR_INGESTION_CRONS = ["30 6 * * *"]
OPTIONS_ACTIVITY_CRONS = ["15 21 * * *"]
MACRO_CALENDAR_INGESTION_CRONS = ["5 11 * * *"]
# F2: post-market TLH scan that snapshots tlh_scan_results so CLI reads
# stay O(1). 13:00 UTC ~ 9:00 ET, weekdays only; the scan reads the
# most recent cached close so timing is robust to weekends/holidays.
TLH_SCAN_CRONS = ["0 13 * * 1-5"]

# F3: daily IPS drift snapshot. 18:00 UTC ~ 1pm ET — well after the
# US market close so the close prices the drift calculation uses are
# stable. Re-runs are idempotent thanks to the composite PK on
# ips_drift_history.
IPS_DRIFT_SNAPSHOT_CRONS = ["0 18 * * *"]

# F4: pre-warm earnings + ex-dividend cache and refresh fomc_meetings
# every morning before the open so /api/catalysts/upcoming is fast
# during the trading day.
CATALYST_PREWARM_CRONS = ["0 6 * * *"]

# Warm price_cache for held household symbols throughout the trading day so
# household dashboard / net-worth-trend reads hit cache instead of paying
# vendor latency. Tiered cadence — every 5 min during regular hours (where
# price moves matter most), every 15 min during pre-market and after-hours
# (where activity is thinner). Weekdays only. UTC windows cover both EST and
# EDT; combined with the session-aware extractor in yfinance_parsers, this
# means the cache reflects the freshest available quote across regular,
# pre-market, and post-market sessions.
HOUSEHOLD_HOLDINGS_REFRESH_CRONS = [
    "*/5 13-20 * * 1-5",  # regular hours (~9:30am-4pm ET both DST regimes)
    "*/15 8-12,21-23 * * 1-5",  # pre-market + after-hours
]

# Recurring sync of "data services" account aggregators (SnapTrade, Plaid).
# Brokerage feeds (e.g. Fidelity via SnapTrade) post holdings/activity on an
# end-of-day cadence and both vendor APIs are rate-limited, so 3x on weekdays
# is the sweet spot: catch overnight postings pre-market, a midday top-up, and
# same-day fills after the close. Weekday-only; the task body is also gated on
# the scheduled_account_sync_enabled preference so users can pause it.
ACCOUNT_SYNC_CRONS = [
    "0 11 * * 1-5",  # pre-market (~6am EST / 7am EDT)
    "0 17 * * 1-5",  # midday (~12pm EST / 1pm EDT)
    "30 21 * * 1-5",  # after close (~4:30pm EST / 5:30pm EDT)
]
