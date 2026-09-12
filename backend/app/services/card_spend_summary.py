"""One deduplicated card spending total for the wallet and card alerts."""
from datetime import date
from typing import Any

from app.services.household_transaction_service import HouseholdTransactionService


def card_spend_summary(storage: Any) -> dict[str, float | str]:
    today = date.today()
    with storage.connection() as conn:
        accounts = {str(row[0]) for row in conn.execute("SELECT DISTINCT household_account_id FROM household_credit_cards WHERE household_account_id IS NOT NULL").fetchall()}
    rows = HouseholdTransactionService(storage=storage)._spend_rows_between(start_date=today.replace(day=1), end_date=today)
    selected = [row for row in rows if row.get("household_account_id") in accounts]
    total = sum(float(row.get("signed_amount", row["amount"])) for row in selected)
    provisional = sum(float(row.get("signed_amount", row["amount"])) for row in selected if row.get("pending"))
    return {"month": today.strftime('%Y-%m'), "total": round(total, 2), "provisional": round(provisional, 2),
            "posted": round(total-provisional, 2), "scope": "Recorded card accounts; posted and provisional purchases with refunds and duplicates netted."}
