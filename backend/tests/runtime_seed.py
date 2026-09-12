"""Synthetic two-month evidence for the isolated running-stack browser suite."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import psycopg


def seed_review_history(conn, today=None) -> None:
    today = today or datetime.now(ZoneInfo("America/New_York")).date()
    previous = today.replace(day=1) - timedelta(days=1)
    account = str(uuid5(NAMESPACE_URL, "portfolio-ai:runtime:account"))
    document = str(uuid5(NAMESPACE_URL, "portfolio-ai:runtime:document"))
    conn.execute(
        """INSERT INTO household_accounts
        (id,canonical_label,asset_group,account_type,source_type,metadata,created_at,updated_at)
        VALUES (%s,'Browser fixture checking','cash','checking','bank',
        '{"synthetic_runtime_fixture":true}'::jsonb,NOW(),NOW()) ON CONFLICT (id) DO NOTHING""",
        [account],
    )
    conn.execute(
        """INSERT INTO household_documents
        (id,filename,stored_path,source_type,document_type,status,content_type,file_size_bytes,
         uploaded_at,parsed_at,metadata,review_status)
        VALUES (%s,'Synthetic browser evidence','api://runtime-fixture','bank','statement',
        'parsed','application/json',0,NOW(),NOW(),'{"synthetic_runtime_fixture":true}'::jsonb,
        'complete') ON CONFLICT (id) DO NOTHING""",
        [document],
    )
    # Exercise a degraded but loaded macro view without relying on external
    # vendor credentials. Every component remains explicitly unavailable.
    conn.execute(
        """INSERT INTO signal_macro_snapshots
        (snapshot_date,deployment_score,zone,raw_json,computed_at)
        VALUES (%s,50,'REDUCED',
        '{"synthetic_runtime_fixture":true,"coverage":0,"degraded":true}'::jsonb,NOW())
        ON CONFLICT (snapshot_date) DO NOTHING""",
        [today],
    )
    for on in [previous, today]:
        for flow, category, amount in [
            ("income", "Income", 3000),
            ("expense", "Groceries", 125),
            ("expense", "Household", 75),
        ]:
            key = f"runtime-fixture:{on.isoformat()}:{category}"
            conn.execute(
                """INSERT INTO household_transactions
                (id,document_id,household_account_id,row_hash,transaction_date,description,
                 raw_merchant,amount,currency,flow_type,category,confidence,metadata,source_system,
                 categorization_source,categorization_version,pending,removed,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'USD',%s,%s,1,
                '{"synthetic_runtime_fixture":true}'::jsonb,'manual','manual','runtime-fixture',
                FALSE,FALSE,NOW(),NOW()) ON CONFLICT (id) DO NOTHING""",
                [
                    str(uuid5(NAMESPACE_URL, key)),
                    document,
                    account,
                    key,
                    on,
                    f"Synthetic {category}",
                    f"Synthetic {category}",
                    amount,
                    flow,
                    category,
                ],
            )


def main() -> None:
    url = os.environ.get("PORTFOLIO_DB_URL", "")
    database = urlparse(url).path.removeprefix("/")
    if os.environ.get("GITHUB_ACTIONS") != "true" or not database.endswith("_test"):
        raise RuntimeError("Runtime fixtures require GitHub Actions and an explicit test database.")
    with psycopg.connect(url) as conn:
        actual = conn.execute("SELECT current_database()").fetchone()
        if not actual or actual[0] != database:
            raise RuntimeError("Runtime fixture database identity does not match.")
        seed_review_history(conn)
    print("Synthetic browser review evidence is ready.")


if __name__ == "__main__":
    main()
