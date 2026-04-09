'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  type TooltipValueType,
  XAxis,
  YAxis,
} from 'recharts'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { formatCurrency, formatCurrencyWhole } from '@/lib/formatters'

const allocationColors = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
]

function formatMonthLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('en-US', {
    month: 'short',
    year: '2-digit',
  })
}

function formatAssetGroup(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())
}

function getTooltipNumber(value: TooltipValueType | undefined): number | null {
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  if (Array.isArray(value)) {
    const parsed = Number(value[0])
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function formatThousandsAxis(value: number) {
  return `$${Math.round(value / 1000)}k`
}

const currencyTooltipFormatter: TooltipProps<TooltipValueType>['formatter'] = (
  value,
) => formatCurrency(getTooltipNumber(value), { decimals: 0, nullDisplay: '—' })

const monthTooltipLabelFormatter: TooltipProps<TooltipValueType>['labelFormatter'] =
  (label) =>
    formatMonthLabel(typeof label === 'string' ? label : String(label ?? ''))

export function MoneyOverviewPanel({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const allocationData = Object.entries(
    dashboard.accounts.reduce<Record<string, number>>((totals, account) => {
      if (
        ['credit', 'debt'].includes(account.assetGroup) ||
        (account.currentValue ?? 0) <= 0
      ) {
        return totals
      }
      totals[account.assetGroup] =
        (totals[account.assetGroup] ?? 0) + (account.currentValue ?? 0)
      return totals
    }, {}),
  )
    .map(([assetGroup, value]) => ({
      assetGroup,
      label: formatAssetGroup(assetGroup),
      value,
    }))
    .sort((left, right) => right.value - left.value)
  const categoryData = dashboard.reports.categoryBreakdown
    .slice()
    .sort((left, right) => right.totalSpend - left.totalSpend)
    .slice(0, 6)
    .map((category) => ({
      category: category.category,
      totalSpend: category.totalSpend,
      monthlyAverage: category.monthlyAverage,
      shareOfSpend: category.shareOfSpend,
    }))

  const [selectedAssetGroup, setSelectedAssetGroup] = useState<string | null>(
    allocationData[0]?.assetGroup ?? null,
  )
  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    categoryData[0]?.category ?? null,
  )

  useEffect(() => {
    if (
      !allocationData.some((item) => item.assetGroup === selectedAssetGroup)
    ) {
      setSelectedAssetGroup(allocationData[0]?.assetGroup ?? null)
    }
  }, [allocationData, selectedAssetGroup])

  useEffect(() => {
    if (!categoryData.some((item) => item.category === selectedCategory)) {
      setSelectedCategory(categoryData[0]?.category ?? null)
    }
  }, [categoryData, selectedCategory])

  const selectedAccounts = dashboard.accounts.filter(
    (account) => account.assetGroup === selectedAssetGroup,
  )
  const selectedTransactions = dashboard.reports.recentTransactions.filter(
    (transaction) => transaction.category === selectedCategory,
  )

  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <div className="space-y-6">
        <SectionCard
          variant="surface"
          title="Account Allocation"
        >
          {allocationData.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
              No asset allocation yet. Upload bank, brokerage, or retirement
              evidence so Jenny can map account balances.
            </div>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={allocationData}
                      dataKey="value"
                      nameKey="label"
                      innerRadius={58}
                      outerRadius={92}
                      paddingAngle={2}
                      onClick={(_, index) => {
                        const entry = allocationData[index]
                        if (entry?.assetGroup) {
                          setSelectedAssetGroup(entry.assetGroup)
                        }
                      }}
                    >
                      {allocationData.map((entry, index) => (
                        <Cell
                          key={entry.assetGroup}
                          fill={
                            allocationColors[index % allocationColors.length]
                          }
                        />
                      ))}
                    </Pie>
                    <Tooltip formatter={currencyTooltipFormatter} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-3">
                {allocationData.map((entry, index) => {
                  const isActive = entry.assetGroup === selectedAssetGroup
                  return (
                    <button
                      key={entry.assetGroup}
                      type="button"
                      onClick={() => setSelectedAssetGroup(entry.assetGroup)}
                      className={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition-colors ${
                        isActive
                          ? 'border-primary/40 bg-primary/10'
                          : 'border-border/40 bg-surface-muted/15 hover:border-border/60'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className="h-3 w-3 rounded-full"
                          style={{
                            backgroundColor:
                              allocationColors[index % allocationColors.length],
                          }}
                        />
                        <div>
                          <p className="text-sm font-semibold text-text">
                            {entry.label}
                          </p>
                          <p className="text-xs text-text-muted">
                            {
                              dashboard.accounts.filter(
                                (account) =>
                                  account.assetGroup === entry.assetGroup,
                              ).length
                            }{' '}
                            account
                            {dashboard.accounts.filter(
                              (account) =>
                                account.assetGroup === entry.assetGroup,
                            ).length === 1
                              ? ''
                              : 's'}
                          </p>
                        </div>
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-text">
                        {formatCurrencyWhole(entry.value)}
                      </span>
                    </button>
                  )
                })}
                {selectedAccounts.length > 0 ? (
                  <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                      Drill-down
                    </p>
                    <div className="mt-3 space-y-2">
                      {selectedAccounts.slice(0, 4).map((account) => (
                        <div
                          key={account.id}
                          className="flex items-center justify-between gap-3 text-sm"
                        >
                          <div>
                            <p className="font-medium text-text">
                              {account.label}
                            </p>
                            <p className="text-xs text-text-muted">
                              {account.freshnessLabel} · {account.matchStatus}
                            </p>
                          </div>
                          <span className="tabular-nums text-text">
                            {formatCurrencyWhole(account.currentValue)}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4">
                      <Button asChild size="sm" variant="outline">
                        <Link href="/money?tab=accounts">
                          Open account cards
                        </Link>
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          )}
        </SectionCard>

        <SectionCard
          variant="surface"
          title="Monthly Spend Trend"
        >
          {dashboard.reports.monthlySpendTrend.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
              No monthly spend trend yet. Upload at least one
              transaction-bearing statement or export.
            </div>
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={dashboard.reports.monthlySpendTrend}
                  margin={{ top: 10, right: 12, left: 0, bottom: 8 }}
                >
                  <XAxis
                    dataKey="month"
                    tickFormatter={formatMonthLabel}
                    tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                    axisLine={{ stroke: 'var(--color-border)' }}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={formatThousandsAxis}
                    tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                  />
                  <Tooltip
                    formatter={currencyTooltipFormatter}
                    labelFormatter={monthTooltipLabelFormatter}
                  />
                  <Line
                    type="monotone"
                    dataKey="totalSpend"
                    stroke="var(--color-chart-blue)"
                    strokeWidth={2.5}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </SectionCard>
      </div>

      <SectionCard
        variant="surface"
        title="Spending Categories"
      >
        {categoryData.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
            Category visuals will appear once Jenny has enough transaction
            history to categorize your spending.
          </div>
        ) : (
          <div className="space-y-5">
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={categoryData}
                  layout="vertical"
                  margin={{ top: 10, right: 12, left: 12, bottom: 8 }}
                >
                  <XAxis
                    type="number"
                    tickFormatter={formatThousandsAxis}
                    tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="category"
                    width={90}
                    tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip formatter={currencyTooltipFormatter} />
                  <Bar
                    dataKey="totalSpend"
                    radius={[0, 10, 10, 0]}
                    onClick={(_, index) => {
                      const entry = categoryData[index]
                      if (entry?.category) {
                        setSelectedCategory(entry.category)
                      }
                    }}
                  >
                    {categoryData.map((entry) => (
                      <Cell
                        key={entry.category}
                        fill={
                          entry.category === selectedCategory
                            ? 'var(--color-chart-orange)'
                            : 'var(--color-chart-cyan)'
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-text">
                    {selectedCategory ?? 'Recent category'}
                  </p>
                  <p className="text-xs text-text-muted">
                    {selectedTransactions.length > 0
                      ? 'Recent transactions behind this category.'
                      : 'No recent transactions are visible for this category yet.'}
                  </p>
                </div>
                {selectedCategory ? (
                  <button
                    type="button"
                    onClick={() => setSelectedCategory(null)}
                    className="text-xs font-medium text-text-muted transition-colors hover:text-text"
                  >
                    Clear
                  </button>
                ) : null}
              </div>
              <div className="mt-4 space-y-2">
                {(selectedCategory
                  ? selectedTransactions
                  : dashboard.reports.recentTransactions
                )
                  .slice(0, 6)
                  .map((transaction) => (
                    <div
                      key={`${transaction.date}-${transaction.description}-${transaction.amount}`}
                      className="flex items-center justify-between gap-3 rounded-xl border border-border/30 bg-surface/60 px-3 py-2"
                    >
                      <div>
                        <p className="text-sm font-medium text-text">
                          {transaction.merchant}
                        </p>
                        <p className="text-xs text-text-muted">
                          {transaction.date} · {transaction.category}
                        </p>
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-text">
                        {formatCurrencyWhole(transaction.amount)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
