'use client'

import { useMemo, useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { formatCurrency, formatPercent } from '@/lib/formatters'
import { formatBudgetDate } from './budget-helpers'
import { allocationColors } from './overview-helpers'
import type { OwnerSpendRow } from './useBudgetRows'

interface OwnerSpendInsightsCardProps {
  timeframeLabel: string | undefined
  ownerSpendRows: OwnerSpendRow[]
}

export function OwnerSpendInsightsCard({
  timeframeLabel,
  ownerSpendRows,
}: OwnerSpendInsightsCardProps) {
  const [selectedOwner, setSelectedOwner] = useState<string | null>(null)
  const activeOwnerName =
    selectedOwner &&
    ownerSpendRows.some((row) => row.ownerName === selectedOwner)
      ? selectedOwner
      : (ownerSpendRows[0]?.ownerName ?? null)
  const activeOwner = ownerSpendRows.find(
    (row) => row.ownerName === activeOwnerName,
  )
  const totalSpend = useMemo(
    () => ownerSpendRows.reduce((sum, row) => sum + row.totalSpend, 0),
    [ownerSpendRows],
  )

  return (
    <SectionCard
      variant="surface"
      title="Owner spend"
      description={`Who is spending what across ${timeframeLabel ?? 'the selected window'}. Item owners win first; category owners fill the rest.`}
    >
      {ownerSpendRows.length === 0 || totalSpend <= 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
          No owner spend is available yet. Set category owners or item owners to
          build the chart.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
          <div className="h-72">
            <ResponsiveContainer
              width="100%"
              height="100%"
              minWidth={240}
              minHeight={260}
              initialDimension={{ width: 360, height: 280 }}
            >
              <PieChart>
                <Pie
                  data={ownerSpendRows}
                  dataKey="totalSpend"
                  nameKey="ownerName"
                  innerRadius={58}
                  outerRadius={94}
                  paddingAngle={2}
                  onClick={(_, index) => {
                    const entry = ownerSpendRows[index]
                    if (entry) {
                      setSelectedOwner(entry.ownerName)
                    }
                  }}
                >
                  {ownerSpendRows.map((entry, index) => (
                    <Cell
                      key={entry.ownerName}
                      fill={allocationColors[index % allocationColors.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) =>
                    formatCurrency(Number(value), { decimals: 2 })
                  }
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-3">
            {ownerSpendRows.map((row, index) => {
              const isActive = row.ownerName === activeOwnerName
              return (
                <button
                  key={row.ownerName}
                  type="button"
                  onClick={() => setSelectedOwner(row.ownerName)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors ${
                    isActive
                      ? 'border-primary/40 bg-primary/10'
                      : 'border-border/40 bg-surface-muted/15 hover:border-border/60'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <span
                        className="h-3 w-3 rounded-full"
                        style={{
                          backgroundColor:
                            allocationColors[index % allocationColors.length],
                        }}
                      />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-text">
                          {row.ownerName}
                        </p>
                        <p className="text-xs text-text-muted">
                          {row.transactionCount} transaction
                          {row.transactionCount === 1 ? '' : 's'} ·{' '}
                          {formatPercent(row.shareOfSpend * 100, {
                            decimals: 0,
                          })}{' '}
                          of owner-attributed spend
                        </p>
                      </div>
                    </div>
                    <span className="font-mono text-sm tabular-nums text-text">
                      {formatCurrency(row.totalSpend, { decimals: 2 })}
                    </span>
                  </div>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{
                        width: `${Math.min(row.shareOfSpend * 100, 100)}%`,
                      }}
                    />
                  </div>
                </button>
              )
            })}

            {activeOwner ? (
              <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                      Drill-down
                    </p>
                    <p className="mt-1 text-sm font-semibold text-text">
                      {activeOwner.ownerName}
                    </p>
                  </div>
                  <Badge variant="outline">
                    {formatCurrency(activeOwner.totalSpend, { decimals: 2 })}
                  </Badge>
                </div>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
                      Categories
                    </p>
                    <div className="mt-2 space-y-2">
                      {activeOwner.categories.slice(0, 6).map((category) => (
                        <div
                          key={category.category}
                          className="flex items-center justify-between gap-3 text-sm"
                        >
                          <span className="min-w-0 truncate text-text">
                            {category.category}
                          </span>
                          <span className="font-mono tabular-nums text-text-muted">
                            {formatCurrency(category.totalSpend, {
                              decimals: 2,
                            })}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
                      Recent rows
                    </p>
                    <div className="mt-2 max-h-52 space-y-2 overflow-auto pr-1">
                      {activeOwner.transactions.slice(0, 8).map((row) => (
                        <div
                          key={row.id}
                          className="rounded-xl border border-border/30 bg-surface/50 px-3 py-2 text-xs"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <span className="min-w-0 truncate font-medium text-text">
                              {row.merchant}
                            </span>
                            <span className="font-mono tabular-nums text-text">
                              {formatCurrency(row.amount, { decimals: 2 })}
                            </span>
                          </div>
                          <p className="mt-1 text-text-muted">
                            {formatBudgetDate(row.date)} · {row.category} ·{' '}
                            {row.ownerSource === 'item'
                              ? 'item owner'
                              : row.ownerSource === 'category'
                                ? 'category owner'
                                : 'unassigned'}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </SectionCard>
  )
}
