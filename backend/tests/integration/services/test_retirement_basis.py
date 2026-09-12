import uuid
from types import SimpleNamespace

import pytest
from tests.integration.services.test_household_transaction_dedup import _insert_account

from app.portfolio.price_fetcher import PriceDataFetcher
from app.services.retirement_basis import RetirementBasisService, summarize_basis
from app.storage import get_storage


def test_basis_matches_canonical_alias_and_expires_when_holdings_change(monkeypatch):
    storage=get_storage()
    hid=_insert_account(storage)
    pid=str(uuid.uuid4())
    with storage.connection() as conn:
        conn.execute("INSERT INTO symbols (symbol,company_name) VALUES ('VTI','Total Stock Market ETF') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO portfolio_accounts(id,name,account_type,household_account_id) VALUES (%s,'Basis account','Taxable',%s)",[pid,hid])
        conn.execute("INSERT INTO portfolio_positions(id,account_id,symbol,shares,cost_basis,position_type) VALUES (%s,%s,'VTI',100,60,'long')",[str(uuid.uuid4()),pid])
        conn.commit()
    monkeypatch.setattr(PriceDataFetcher,'fetch_cached_price_data',lambda *_: {'VTI':SimpleNamespace(price=100,error=None)})
    account=SimpleNamespace(household_account_id=hid,linked_portfolio_account_id='old-alias',
        label='Taxable',asset_group='taxable',account_type='Taxable',current_value=10000,cash_balance=0)
    dashboard=SimpleNamespace(accounts=[account,SimpleNamespace(asset_group='education',account_type='Taxable',current_value=100000)])
    service=RetirementBasisService(storage)
    report=service.coverage(dashboard)
    assert len(report['accounts'])==1
    assert len(report['accounts'][0]['positions'])==1
    # Stored position cost can be a price fallback: do not claim verified basis.
    assert report['coverage']==0
    with pytest.raises(ValueError,match='changed'):
        service.confirm(dashboard,hid,'bad',6000)
    service.confirm(dashboard,hid,report['accounts'][0]['fingerprint'],6000)
    confirmed=service.coverage(dashboard)
    assert confirmed['coverage']==1
    assert confirmed['gain_ratio']==pytest.approx(.4)
    with storage.connection() as conn:
        conn.execute('UPDATE portfolio_positions SET shares=101 WHERE account_id=%s',[pid])
        conn.commit()
    assert service.coverage(dashboard)['accounts'][0]['confirmation_stale']


def test_partial_basis_only_applies_known_gains_to_covered_value():
    report=summarize_basis([{'market_value':10000,'covered_value':1000,'cost_basis':600,'known_gain':400}])
    assert report['coverage']==.1
    assert report['gain_ratio']==pytest.approx(.175)
    assert report['gain_ratio_low']==.04
    assert report['gain_ratio_high']==.94
