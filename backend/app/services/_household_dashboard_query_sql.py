"""SQL constants for household dashboard query helpers."""

from __future__ import annotations

from app.services._household_recurrence import MIN_SIGHTINGS
from app.services._household_spend_filters import (
    investment_activity_sql_predicate,
    non_spend_sql_predicate,
)


def current_transaction_date_predicate(alias: str | None = None) -> str:
    qualifier = f"{alias}." if alias else ""
    return f"{qualifier}transaction_date <= CURRENT_DATE"


_NON_SPEND_TRANSACTION_SQL = non_spend_sql_predicate(
    text_expressions=["t.description", "t.raw_merchant"],
    category_expression="t.category",
    override_expression="t.spend_override",
)
_INVESTMENT_ACTIVITY_SQL = investment_activity_sql_predicate(
    text_expressions=["description", "raw_merchant"],
)

CATEGORIZATION_SQL = f"""
    SELECT
        t.id,
        COALESCE(t.raw_merchant, t.description) AS merchant,
        t.description,
        t.amount,
        t.transaction_date,
        t.category,
        t.essentiality,
        t.confidence,
        COALESCE(similar_txns.similar_count, 0) AS similar_count,
        COALESCE(t.metadata->'audit'->>'reason', '') AS audit_reason,
        COALESCE(t.metadata->'audit'->>'suggested_category', '') AS audit_suggested_category,
        COALESCE(t.metadata->'audit'->>'suggested_essentiality', '') AS audit_suggested_essentiality
    FROM household_transactions t
    LEFT JOIN (
        SELECT t.merchant_id, COUNT(*) AS similar_count
        FROM household_transactions t
        WHERE t.flow_type = 'expense'
          AND {current_transaction_date_predicate("t")}
          AND NOT {_NON_SPEND_TRANSACTION_SQL}
        GROUP BY merchant_id
    ) similar_txns ON similar_txns.merchant_id = t.merchant_id
    WHERE t.flow_type = 'expense'
      AND {current_transaction_date_predicate("t")}
      AND NOT {_NON_SPEND_TRANSACTION_SQL}
      AND (
            COALESCE(t.confidence, 0) < 0.60
         OR COALESCE(t.metadata->'audit'->>'status', '') = 'needs_review'
      )
    ORDER BY CAST(t.amount AS DOUBLE PRECISION) DESC, COALESCE(similar_txns.similar_count, 0) DESC
    LIMIT %s
"""

RECURRING_SQL = f"""
    SELECT
        COALESCE(m.canonical_name, t.raw_merchant, t.description) AS merchant,
        mode() WITHIN GROUP (ORDER BY COALESCE(t.category, 'Household')) AS category,
        array_agg(t.transaction_date::date ORDER BY t.transaction_date) AS charge_dates,
        array_agg(CAST(t.amount AS DOUBLE PRECISION) ORDER BY t.transaction_date) AS charge_amounts,
        BOOL_OR(jsonb_exists(COALESCE(m.metadata, '{{}}'::jsonb), 'cadence_override')) AS cadence_declared
    FROM household_transactions t
    LEFT JOIN household_merchants m ON m.id = t.merchant_id
    WHERE t.flow_type = 'expense'
      AND t.removed IS NOT TRUE
      AND {current_transaction_date_predicate("t")}
      AND NOT {_NON_SPEND_TRANSACTION_SQL}
    GROUP BY 1
    -- The whole charge series comes back per merchant because periodicity and
    -- amount stability cannot be judged from an average and a count. There is
    -- deliberately no ORDER BY average_amount here: ranking merchants by size
    -- before testing whether they recur at all is what put a two-week Airbnb
    -- stay at the top of the household's recurring bills.
    --
    -- {MIN_SIGHTINGS} sightings is the floor for inferring a rhythm. A merchant
    -- whose cadence the household has declared is admitted on one, which is the
    -- only way an annual obligation ever reaches a sinking fund. jsonb_exists,
    -- not the containment operator -- the driver reads that operator's
    -- character as a placeholder.
    HAVING COUNT(*) >= {MIN_SIGHTINGS}
        OR BOOL_OR(jsonb_exists(COALESCE(m.metadata, '{{}}'::jsonb), 'cadence_override'))
"""

RETIREMENT_CONTRIBUTION_SQL = f"""
    SELECT AVG(month_total)
    FROM (
        SELECT
            date_trunc('month', transaction_date) AS month_bucket,
            SUM(CAST(amount AS DOUBLE PRECISION)) AS month_total
        FROM household_transactions
        WHERE flow_type IN ('transfer_out', 'expense')
          AND {current_transaction_date_predicate()}
          AND (
            COALESCE(account_label, '') ILIKE '%ira%'
            OR COALESCE(account_label, '') ILIKE '%401%'
            OR COALESCE(account_label, '') ILIKE '%roth%'
            OR COALESCE(account_label, '') ILIKE '%hsa%'
          )
        GROUP BY 1
    ) monthly_contributions
"""

MONTH_SPEND_SQL = f"""
    SELECT COALESCE(SUM(CAST(amount AS DOUBLE PRECISION)), 0)
    FROM household_transactions t
    WHERE t.flow_type = 'expense'
      AND t.transaction_date >= date_trunc('month', CURRENT_DATE)
      AND {current_transaction_date_predicate("t")}
      AND NOT {_NON_SPEND_TRANSACTION_SQL}
"""

STATEMENT_FRESHNESS_SQL = f"""
    WITH monthly_expenses AS (
        SELECT
            date_trunc('month', t.transaction_date)::date AS month_start,
            MAX(t.transaction_date)::date AS month_last_date
        FROM household_transactions t
        WHERE t.flow_type = 'expense'
          AND {current_transaction_date_predicate("t")}
          AND NOT {_NON_SPEND_TRANSACTION_SQL}
        GROUP BY 1
    ),
    recent_months AS (
        SELECT
            month_start,
            month_last_date,
            ROW_NUMBER() OVER (ORDER BY month_start DESC) AS recency_rank
        FROM monthly_expenses
    )
    SELECT
        MAX(month_last_date) AS most_recent_date,
        COUNT(*) AS coverage_months,
        MIN(month_start) AS earliest_date
    FROM recent_months
    WHERE recency_rank <= 6
"""

FUTURE_TRANSACTION_QUALITY_SQL = """
    SELECT
        COUNT(*) AS future_transaction_count,
        MIN(transaction_date) AS earliest_future_date,
        MAX(transaction_date) AS latest_future_date
    FROM household_transactions
    WHERE transaction_date > CURRENT_DATE
"""

DOCUMENT_FUTURE_TRANSACTION_QUALITY_SQL = """
    SELECT
        COUNT(*) AS future_transaction_count,
        MIN((future_txn->>'transaction_date')::date) AS earliest_future_date,
        MAX((future_txn->>'transaction_date')::date) AS latest_future_date
    FROM household_documents d
    CROSS JOIN LATERAL jsonb_array_elements(
        COALESCE(d.metadata->'date_quality_summary'->'future_transactions', '[]'::jsonb)
    ) AS future_txn
    WHERE d.metadata->'date_quality_summary'->>'status' = 'needs_review'
      AND NOT EXISTS (
          SELECT 1
          FROM household_transactions t
          WHERE t.document_id = d.id
            AND t.transaction_date > CURRENT_DATE
      )
"""

CONFIRMED_FACTS_SQL = """
    SELECT fact_key, fact_value
    FROM household_confirmed_facts
"""

LATEST_TRANSACTION_DATE_SQL = {
    "document_id": """
        SELECT document_id, MAX(transaction_date) AS latest_transaction_date
        FROM household_transactions
        WHERE document_id IS NOT NULL
        GROUP BY document_id
    """,
    "account_label": """
        SELECT account_label, MAX(transaction_date) AS latest_transaction_date
        FROM household_transactions
        WHERE account_label IS NOT NULL
        GROUP BY account_label
    """,
    "household_account_id": """
        SELECT household_account_id, MAX(transaction_date) AS latest_transaction_date
        FROM household_transactions
        WHERE household_account_id IS NOT NULL
        GROUP BY household_account_id
    """,
}

INCOME_MONTHLY_AVG_SQL = f"""
    SELECT
        COUNT(*) AS months_with_income,
        AVG(month_total) AS avg_monthly_income
    FROM (
        SELECT
            date_trunc('month', transaction_date) AS month_bucket,
            SUM(CAST(amount AS DOUBLE PRECISION)) AS month_total
        FROM household_transactions
        WHERE flow_type = 'income'
          AND {current_transaction_date_predicate()}
          AND NOT {_INVESTMENT_ACTIVITY_SQL}
        GROUP BY 1
    ) monthly_income
"""
