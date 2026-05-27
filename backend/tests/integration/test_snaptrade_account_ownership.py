"""Integration tests for SnapTrade spouse/owner attribution.

Covers the reconciliation that derives ``portfolio_accounts.is_spouse`` from
connection ownership. The central guarantee: a joint account surfaced under
both spouses' logins stays attributed to the household (never to one person),
and attribution is purely a label — it must never gate balances or totals.
"""

from __future__ import annotations

import uuid

import pytest

from app.services.snaptrade_service import SnapTradeService


def _seed(conn, *, user_id: str) -> None:
    conn.execute(
        """
        INSERT INTO snaptrade_users (id, user_id, user_secret_ciphertext, status)
        VALUES (%s, %s, %s, 'active')
        """,
        [str(uuid.uuid4()), user_id, "ciphertext"],
    )
    # Two logins: one is the spouse's, one is the primary's.
    for auth_id, owner_is_spouse, owner_name in (
        ("auth-spouse", True, "Mariana"),
        ("auth-primary", False, None),
    ):
        conn.execute(
            """
            INSERT INTO snaptrade_connections (
                id, user_id, authorization_id, connection_type,
                owner_is_spouse, owner_name
            ) VALUES (%s, %s, %s, 'read', %s, %s)
            """,
            [str(uuid.uuid4()), user_id, auth_id, owner_is_spouse, owner_name],
        )
    # Three canonical accounts: spouse-sole, primary-sole, and joint.
    for pid, name, acct_type in (
        ("pa-spouse", "Rollover IRA", "IRA"),
        ("pa-primary", "Traditional IRA", "IRA"),
        ("pa-joint", "Cash Management (Joint WROS)", "Taxable"),
    ):
        conn.execute(
            """
            INSERT INTO portfolio_accounts (id, name, account_type, cash_balance, initial_cash, is_spouse)
            VALUES (%s, %s, %s, 0, 0, FALSE)
            """,
            [pid, name, acct_type],
        )
    # snaptrade_accounts link source rows to connections. The joint account is
    # surfaced by BOTH logins (two source rows, same portfolio_account_id).
    links = [
        ("sa-spouse", "auth-spouse", "pa-spouse"),
        ("sa-primary", "auth-primary", "pa-primary"),
        ("sa-joint-spouse", "auth-spouse", "pa-joint"),
        ("sa-joint-primary", "auth-primary", "pa-joint"),
    ]
    for account_id, auth_id, pid in links:
        conn.execute(
            """
            INSERT INTO snaptrade_accounts (
                id, user_id, account_id, authorization_id,
                portfolio_account_id, name, portfolio_account_type
            ) VALUES (%s, %s, %s, %s, %s, %s, 'Taxable')
            """,
            [str(uuid.uuid4()), user_id, account_id, auth_id, pid, "Account"],
        )
    conn.commit()


def _is_spouse_map(conn) -> dict[str, bool]:
    rows = conn.execute("SELECT id, is_spouse FROM portfolio_accounts").fetchall()
    return {str(r[0]): bool(r[1]) for r in rows}


@pytest.mark.usefixtures("clean_database")
def test_reconcile_attributes_sole_spouse_accounts_and_keeps_joint_household() -> None:
    service = SnapTradeService()
    with service.storage.connection() as conn:
        _seed(conn, user_id=f"user-{uuid.uuid4()}")

    service._reconcile_account_ownership()

    with service.storage.connection() as conn:
        flags = _is_spouse_map(conn)

    assert flags["pa-spouse"] is True, "account only under the spouse login is spouse-owned"
    assert flags["pa-primary"] is False, "account only under the primary login is not spouse-owned"
    assert flags["pa-joint"] is False, "joint account under both logins stays household-owned"


@pytest.mark.usefixtures("clean_database")
def test_set_connection_owner_persists_and_reapplies_attribution() -> None:
    service = SnapTradeService()
    user_id = f"user-{uuid.uuid4()}"
    with service.storage.connection() as conn:
        # Seed both connections as primary-owned to start.
        conn.execute(
            """
            INSERT INTO snaptrade_users (id, user_id, user_secret_ciphertext, status)
            VALUES (%s, %s, 'ciphertext', 'active')
            """,
            [str(uuid.uuid4()), user_id],
        )
        for auth_id in ("auth-spouse", "auth-primary"):
            conn.execute(
                """
                INSERT INTO snaptrade_connections (
                    id, user_id, authorization_id, connection_type, owner_is_spouse
                ) VALUES (%s, %s, %s, 'read', FALSE)
                """,
                [str(uuid.uuid4()), user_id, auth_id],
            )
        conn.execute(
            """
            INSERT INTO portfolio_accounts (id, name, account_type, cash_balance, initial_cash, is_spouse)
            VALUES ('pa-spouse', 'Rollover IRA', 'IRA', 0, 0, FALSE)
            """,
        )
        conn.execute(
            """
            INSERT INTO snaptrade_accounts (
                id, user_id, account_id, authorization_id,
                portfolio_account_id, name, portfolio_account_type
            ) VALUES (%s, %s, 'sa-spouse', 'auth-spouse', 'pa-spouse', 'Account', 'IRA')
            """,
            [str(uuid.uuid4()), user_id],
        )
        conn.commit()

    result = service.set_connection_owner("auth-spouse", is_spouse=True, owner_name="Mariana")
    assert result["owner_is_spouse"] is True
    assert result["owner_name"] == "Mariana"

    with service.storage.connection() as conn:
        assert _is_spouse_map(conn)["pa-spouse"] is True
        owner = conn.execute(
            "SELECT owner_is_spouse, owner_name FROM snaptrade_connections WHERE authorization_id = 'auth-spouse'"
        ).fetchone()
    assert owner is not None
    assert bool(owner[0]) is True
    assert str(owner[1]) == "Mariana"

    # Reassigning ownership back to the household re-derives attribution.
    service.set_connection_owner("auth-spouse", is_spouse=False)
    with service.storage.connection() as conn:
        assert _is_spouse_map(conn)["pa-spouse"] is False
