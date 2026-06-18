'use client'

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { SectionCard } from '@/components/shared/SectionCard'
import type { HouseholdSpendingTransaction } from '@/lib/api/household'
import { formatCurrency, formatCurrencyWhole } from '@/lib/formatters'
import { formatThousandsAxis } from './budget-helpers'

type ConnectedSpendTransaction = HouseholdSpendingTransaction & {
  sourceSystem?: string | null
}

type TopTransaction = {
  id: string
  date: string
  merchant: string
  amount: number
  accountLabel: string | null
  pending: boolean
}

type WeeklySpendPoint = {
  week: string
  label: string
  totalSpend: number
  transactionCount: number
  pendingCount: number
  change: number | null
  changePct: number | null
  topTransactions: TopTransaction[]
}

function parseDateKey(value: string) {
  const parsed = new Date(`${value}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function dateKey(date: Date) {
  return date.toISOString().slice(0, 10)
}

function weekStartKey(value: string) {
  const parsed = parseDateKey(value)
  if (!parsed) return value
  const day = parsed.getUTCDay()
  const mondayOffset = day === 0 ? -6 : 1 - day
  parsed.setUTCDate(parsed.getUTCDate() + mondayOffset)
  return dateKey(parsed)
}

function formatShortDate(value: string) {
  const parsed = parseDateKey(value)
  if (!parsed) return value
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

function formatWeekLabel(week: string) {
  const parsed = parseDateKey(week)
  if (!parsed) return week
  const end = new Date(parsed)
  end.setUTCDate(parsed.getUTCDate() + 6)
  return `${formatShortDate(week)}–${formatShortDate(dateKey(end))}`
}

function isConnectedAccountTransaction(row: ConnectedSpendTransaction) {
  const source = row.sourceSystem?.toLowerCase()
  return (
    row.sourceKind === 'transaction' &&
    (source === 'plaid' || source === 'snaptrade')
  )
}

function buildWeeklySpendPoints(
  transactions: ConnectedSpendTransaction[],
): WeeklySpendPoint[] {
  const groups = new Map<
    string,
    {
      transactions: ConnectedSpendTransaction[]
      totalSpend: number
      pendingCount: number
    }
  >()

  for (const row of transactions) {
    if (!isConnectedAccountTransaction(row)) continue
    const week = weekStartKey(row.date)
    const group = groups.get(week) ?? {
      transactions: [],
      totalSpend: 0,
      pendingCount: 0,
    }
    group.transactions.push(row)
    group.totalSpend += row.amount
    if (row.pending) group.pendingCount += 1
    groups.set(week, group)
  }

  const points = [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([week, group]) => ({
      week,
      label: formatWeekLabel(week),
      totalSpend: Math.round(group.totalSpend * 100) / 100,
      transactionCount: group.transactions.length,
      pendingCount: group.pendingCount,
      change: null as number | null,
      changePct: null as number | null,
      topTransactions: group.transactions
        .filter((row) => row.amount > 0)
        .sort((left, right) => right.amount - left.amount)
        .slice(0, 5)
        .map((row) => ({
          id: row.id,
          date: row.date,
          merchant: row.merchant || row.description,
          amount: row.amount,
          accountLabel: row.accountLabel ?? null,
          pending: row.pending === true,
        })),
    }))

  return points.map((point, index) => {
    const previous = points[index - 1]
    if (!previous) return point
    const change = point.totalSpend - previous.totalSpend
    return {
      ...point,
      change,
      changePct:
        previous.totalSpend !== 0
          ? change / Math.abs(previous.totalSpend)
          : null,
    }
  })
}

function ConnectedSpendTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: WeeklySpendPoint }>
}) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return (
    <div className="max-w-sm rounded-xl border border-border/60 bg-surface/95 p-3 text-xs shadow-xl">
      <p className="font-semibold text-text">{point.label}</p>
      <p className="mt-1 text-text-muted">
        Connected spend:{' '}
        <span className="font-mono text-text">
          {formatCurrency(point.totalSpend, { decimals: 0 })}
        </span>
        {point.change != null ? (
          <>
            {' '}
            · WoW{' '}
            <span className={point.change >= 0 ? 'text-loss' : 'text-gain'}>
              {point.change >= 0 ? '+' : ''}
              {formatCurrency(point.change, { decimals: 0 })}
              {point.changePct != null
                ? ` (${point.changePct >= 0 ? '+' : ''}${(point.changePct * 100).toFixed(0)}%)`
                : ''}
            </span>
          </>
        ) : null}
      </p>
      <p className="mt-1 text-text-muted">
        {point.transactionCount} Chase/CMA transaction
        {point.transactionCount === 1 ? '' : 's'}
        {point.pendingCount > 0
          ? ` · ${point.pendingCount} pending included`
          : ''}
      </p>
      {point.topTransactions.length > 0 ? (
        <div className="mt-3 space-y-1.5">
          <p className="font-medium text-text-muted">Top transactions</p>
          {point.topTransactions.map((transaction) => (
            <div
              key={transaction.id}
              className="grid grid-cols-[1fr_auto] gap-3 text-text"
            >
              <span className="min-w-0 truncate">
                {formatShortDate(transaction.date)} · {transaction.merchant}
                {transaction.pending ? ' · pending' : ''}
              </span>
              <span className="font-mono">
                {formatCurrency(transaction.amount, { decimals: 0 })}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function ConnectedSpendTrendChart({
  transactions,
  isLoading,
}: {
  transactions: ConnectedSpendTransaction[]
  isLoading: boolean
}) {
  const points = buildWeeklySpendPoints(transactions)

  return (
    <SectionCard
      variant="surface"
      title="Connected spend trend"
      description="Weekly Plaid/SnapTrade spend for the last 12 months, or as much connected history as exists. Hover a week for the top 5 Chase/CMA transactions."
    >
      {isLoading ? (
        <div className="h-72 rounded-2xl skeleton" />
      ) : points.length < 2 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
          Not enough connected account history for a trendline yet.
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-3">
              <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                Latest week
              </p>
              <p className="mt-1 text-lg font-semibold text-text">
                {formatCurrencyWhole(points.at(-1)?.totalSpend)}
              </p>
            </div>
            <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-3">
              <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                Weeks shown
              </p>
              <p className="mt-1 text-lg font-semibold text-text">
                {points.length}
              </p>
            </div>
            <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-3">
              <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                Latest WoW
              </p>
              <p className="mt-1 text-lg font-semibold text-text">
                {points.at(-1)?.change == null
                  ? '—'
                  : formatCurrency(points.at(-1)?.change ?? null, {
                      decimals: 0,
                    })}
              </p>
            </div>
          </div>
          <div className="h-72">
            <ResponsiveContainer
              width="100%"
              height="100%"
              minWidth={240}
              minHeight={288}
              initialDimension={{ width: 720, height: 288 }}
            >
              <LineChart
                data={points}
                margin={{ top: 12, right: 16, left: 0, bottom: 8 }}
              >
                <XAxis
                  dataKey="week"
                  tickFormatter={formatShortDate}
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={{ stroke: 'var(--color-border)' }}
                  tickLine={false}
                  minTickGap={24}
                />
                <YAxis
                  tickFormatter={formatThousandsAxis}
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <Tooltip content={<ConnectedSpendTooltip />} />
                <Line
                  type="monotone"
                  dataKey="totalSpend"
                  name="Connected spend"
                  stroke="var(--color-chart-1)"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
