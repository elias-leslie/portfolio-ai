from datetime import date

import pytest

from app.analytics.portfolio_performance import FlowAdjustedSeries, aligned_returns, sharpe

D1=date(2026,9,8)
D2=date(2026,9,9)
D3=date(2026,9,10)


def test_deposit_and_withdrawal_are_not_returns():
    assert aligned_returns({'a':{D1:100,D2:110}},{('a',D2):10},[D1,D2]).returns == (0,)
    assert aligned_returns({'a':{D1:100,D2:80}},{('a',D2):-20},[D1,D2]).returns == (0,)


def test_new_account_never_creates_a_portfolio_gain():
    series=aligned_returns({'a':{D1:100,D2:100,D3:100},'b':{D2:100,D3:100}},{},[D1,D2,D3])
    assert series.dates == (D2,D3)
    assert series.returns == (0,)


def test_missing_middle_snapshot_does_not_become_daily_return():
    assert aligned_returns({'a':{D1:100,D3:110}},{},[D1,D2,D3]).reason


def test_intraday_flow_uses_explicit_midday_weight():
    assert aligned_returns({'a':{D1:100,D2:121}},{('a',D2):20},[D1,D2]).returns == pytest.approx((1/110,))


def test_sharpe_needs_sixty_observations_and_nonzero_variation():
    assert sharpe(FlowAdjustedSeries(returns=(.01,-.005))) is None
    assert sharpe(FlowAdjustedSeries(returns=(.01,)*60)) is None
    assert sharpe(FlowAdjustedSeries(returns=(.01,-.005)*30)) is not None
