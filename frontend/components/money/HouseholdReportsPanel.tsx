'use client'

import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'

function formatMonthLabel(month: string): string {
  const [year, value] = month.split('-')
  const monthIndex = Number(value) - 1
  const parsedYear = Number(year)
  if (!Number.isFinite(monthIndex) || !Number.isFinite(parsedYear)) {
    return month
  }
  return new Date(parsedYear, monthIndex, 1).toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
  })
}

function spendBarWidth(shareOfSpend: number): string {
  const clamped = Math.min(Math.max(shareOfSpend, 0), 1)
  return `${Math.max(clamped * 100, 6)}%`
}

export function HouseholdReportsPanel({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const { executive, categoryBreakdown, merchantHighlights, monthlySpendTrend, recentTransactions } =
    dashboard.reports
  const displayedMonthlySpendTrend = monthlySpendTrend.slice(-6)
  const maxMonthlySpend = Math.max(
    ...displayedMonthlySpendTrend.map((entry) => entry.totalSpend),
    1,
  )

  const executiveCards = [
    {
      label: 'Average monthly spend',
      value: formatCurrency(executive.averageMonthlySpend, { decimals: 0, nullDisplay: 'Not set' }),
      detail: `${executive.coverageMonths} month${executive.coverageMonths === 1 ? '' : 's'} of evidence`,
    },
    {
      label: 'Essential baseline',
      value: formatCurrency(executive.averageMonthlyEssentials, { decimals: 0, nullDisplay: 'Not set' }),
      detail: 'Recurring needs Jenny sees today',
    },
    {
      label: 'Discretionary baseline',
      value: formatCurrency(executive.averageMonthlyDiscretionary, { decimals: 0, nullDisplay: 'Not set' }),
      detail: 'Flexible spend Jenny can optimize',
    },
    {
      label: 'Recent 30-day spend',
      value: formatCurrency(executive.recent30DaySpend, { decimals: 0, nullDisplay: 'Not set' }),
      detail: `${executive.trackedExpenseCount} tracked expense events`,
    },
  ]

  return (
    <SectionCard
      variant="surface"
      title="Household Cash-Flow Report"
      description={executive.summary}
    >
      <div className="space-y-6">
        <div className="rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/10 via-accent/5 to-surface p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
                Executive view
              </p>
              <p className="mt-3 text-2xl font-semibold tracking-tight text-text">
                {executive.headline}
              </p>
              <p className="mt-2 text-sm leading-6 text-text-muted">{executive.summary}</p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="rounded-2xl border border-border/40 bg-surface/80 px-4 py-3 text-sm text-text-muted">
                <p className="font-semibold text-text">{executive.recurringMerchantCount}</p>
                <p>Recurring merchant patterns</p>
              </div>
              <div className="rounded-2xl border border-border/40 bg-surface/80 px-4 py-3 text-sm text-text-muted">
                <p className="font-semibold text-text">{executive.trackedExpenseCount}</p>
                <p>Tracked expense rows</p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {executiveCards.map((card) => (
            <div
              key={card.label}
              className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
            >
              <p className="text-sm font-medium text-text-muted">{card.label}</p>
              <p className="mt-3 text-2xl font-semibold tracking-tight text-text">{card.value}</p>
              <p className="mt-2 text-sm text-text-muted">{card.detail}</p>
            </div>
          ))}
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-text">Budget pressure map</p>
                <p className="mt-1 text-sm text-text-muted">
                  The highest recurring spend lanes Jenny can optimize first.
                </p>
              </div>
            </div>
            <div className="mt-5 space-y-4">
              {categoryBreakdown.length === 0 ? (
                <p className="text-sm text-text-muted">
                  Jenny needs more normalized transactions to break down spending lanes.
                </p>
              ) : (
                categoryBreakdown.slice(0, 6).map((item) => (
                  <div key={`${item.category}-${item.essentiality}`} className="space-y-2">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <div>
                        <p className="font-semibold text-text">{item.category}</p>
                        <p className="text-text-muted">
                          {formatEnumLabel(item.essentiality, 'mixed')}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-text">
                          {formatCurrency(item.monthlyAverage, { decimals: 0, nullDisplay: 'Not set' })}
                        </p>
                        <p className="text-text-muted">
                          {(item.shareOfSpend * 100).toFixed(0)}% of tracked spend
                        </p>
                      </div>
                    </div>
                    <div className="h-2 rounded-full bg-border/40">
                      <div
                        className="h-2 rounded-full bg-primary"
                        style={{ width: spendBarWidth(item.shareOfSpend) }}
                      />
                    </div>
                  </div>
                ))
              )}
              {categoryBreakdown.length > 6 ? (
                <p className="text-xs text-text-muted">
                  Showing the top 6 of {categoryBreakdown.length} tracked spending lanes.
                </p>
              ) : null}
            </div>
          </div>

          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-5">
            <p className="text-sm font-semibold text-text">Merchant intelligence</p>
            <p className="mt-1 text-sm text-text-muted">
              Jenny’s highest-signal merchant patterns for household budgeting and savings.
            </p>
            <div className="mt-5 space-y-3">
              {merchantHighlights.length === 0 ? (
                <p className="text-sm text-text-muted">
                  No merchant patterns yet. Upload more statements or receipts to strengthen this view.
                </p>
              ) : (
                merchantHighlights.slice(0, 4).map((merchant) => (
                  <div
                    key={merchant.merchant}
                    className="rounded-2xl border border-border/40 bg-surface/80 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-text">{merchant.merchant}</p>
                        <p className="mt-1 text-sm text-text-muted">
                          {merchant.category} · {merchant.cadence}
                        </p>
                      </div>
                      <div className="text-right text-sm">
                        <p className="font-semibold text-text">
                          {formatCurrency(merchant.totalSpend, { decimals: 0, nullDisplay: 'Not set' })}
                        </p>
                        <p className="text-text-muted">
                          Avg ticket {formatCurrency(merchant.averageTicket, { decimals: 0, nullDisplay: 'Not set' })}
                        </p>
                      </div>
                    </div>
                    <p className="mt-3 text-sm text-text-muted">{merchant.recommendation}</p>
                  </div>
                ))
              )}
              {merchantHighlights.length > 4 ? (
                <p className="text-xs text-text-muted">
                  Showing the top 4 of {merchantHighlights.length} merchant patterns.
                </p>
              ) : null}
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-5">
            <p className="text-sm font-semibold text-text">Monthly spend trend</p>
            <p className="mt-1 text-sm text-text-muted">
              Recent trend line from normalized expenses and imported order history.
            </p>
            <div className="mt-5 space-y-3">
              {monthlySpendTrend.length === 0 ? (
                <p className="text-sm text-text-muted">Trend data appears once Jenny has at least one month of spend evidence.</p>
              ) : (
                displayedMonthlySpendTrend.map((point) => (
                  <div key={point.month} className="space-y-2">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <p className="font-semibold text-text">{formatMonthLabel(point.month)}</p>
                      <div className="text-right">
                        <p className="font-semibold text-text">
                          {formatCurrency(point.totalSpend, { decimals: 0, nullDisplay: 'Not set' })}
                        </p>
                        <p className="text-text-muted">
                          {point.transactionCount} transaction{point.transactionCount === 1 ? '' : 's'}
                        </p>
                      </div>
                    </div>
                    <div className="h-2 rounded-full bg-border/40">
                      <div
                        className="h-2 rounded-full bg-accent"
                        style={{
                          width: spendBarWidth(point.totalSpend / maxMonthlySpend),
                        }}
                      />
                    </div>
                  </div>
                ))
              )}
              {monthlySpendTrend.length > displayedMonthlySpendTrend.length ? (
                <p className="text-xs text-text-muted">
                  Showing the latest {displayedMonthlySpendTrend.length} of {monthlySpendTrend.length} months.
                </p>
              ) : null}
            </div>
          </div>

          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-5">
            <p className="text-sm font-semibold text-text">Recent tracked transactions</p>
            <p className="mt-1 text-sm text-text-muted">
              A live audit trail so you can verify what Jenny is using to shape the household plan.
            </p>
            <div className="mt-5 space-y-3">
              {recentTransactions.length === 0 ? (
                <p className="text-sm text-text-muted">
                  No recent transactions yet. Statement and receipt imports will populate this automatically.
                </p>
              ) : (
                recentTransactions.slice(0, 8).map((transaction) => (
                  <div
                    key={`${transaction.date}-${transaction.merchant}-${transaction.amount}`}
                    className="grid gap-1 rounded-2xl border border-border/40 bg-surface/80 px-4 py-3 sm:grid-cols-[1fr_auto]"
                  >
                    <div>
                      <p className="text-sm font-semibold text-text">{transaction.merchant}</p>
                      <p className="mt-1 text-sm text-text-muted">{transaction.description}</p>
                      <p className="mt-1 text-xs uppercase tracking-wide text-text-muted">
                        {transaction.category} · {formatEnumLabel(transaction.essentiality, 'mixed')}
                        {transaction.accountLabel ? ` · ${transaction.accountLabel}` : ''}
                      </p>
                    </div>
                    <div className="text-left sm:text-right">
                      <p className="text-sm font-semibold text-text">
                        {formatCurrency(transaction.amount, { decimals: 0, nullDisplay: 'Not set' })}
                      </p>
                      <p className="mt-1 text-sm text-text-muted">
                        {new Date(transaction.date).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                      </p>
                    </div>
                  </div>
                ))
              )}
              {recentTransactions.length > 8 ? (
                <p className="text-xs text-text-muted">
                  Showing the newest 8 of {recentTransactions.length} tracked transactions.
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </SectionCard>
  )
}
