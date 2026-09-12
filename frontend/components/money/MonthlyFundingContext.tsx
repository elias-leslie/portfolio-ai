'use client'

import Link from 'next/link'
import type { HouseholdConfirmedFact } from '@/lib/api/household'
import { formatCurrency } from '@/lib/formatters'

/** A saved monthly agreement is context, not permission to replace a long-term scenario. */
export function MonthlyFundingContext({
  facts,
  month,
}: {
  facts: HouseholdConfirmedFact[]
  month: string
}) {
  const fact = facts.find((item) => item.factKey === `monthly_review:${month}`)
  if (!fact) return null
  let parsed: unknown
  try {
    parsed = JSON.parse(fact.factValue)
  } catch {
    return null
  }
  if (!parsed || typeof parsed !== 'object') return null
  const record = parsed as Record<string, unknown>
  const amount = (key: string) =>
    typeof record[key] === 'number' &&
    Number.isFinite(record[key]) &&
    record[key] >= 0
      ? formatCurrency(record[key], { decimals: 0 })
      : 'not agreed'
  return (
    <div className="mt-3 rounded-xl border border-border/35 p-3 text-sm">
      <p className="font-medium">Monthly agreement · {month}</p>
      <p className="mt-1">
        Expected take-home {amount('expected_income')} · planned draw{' '}
        {amount('planned_asset_draw')} · ordinary spending{' '}
        {amount('planned_spending')} · other commitments{' '}
        {amount('additional_commitments')}.
      </p>
      <p className="mt-1 text-xs text-text-muted">
        This is the same saved agreement shown in Review. The long-term scenario
        keeps its own income, spending, and withdrawal assumptions; check
        differences before applying a monthly change to future years.
      </p>
      <Link
        href={`/money?tab=spending&month=${encodeURIComponent(month)}`}
        className="mt-1 inline-block text-primary underline"
      >
        Review the funding agreement
      </Link>
    </div>
  )
}
