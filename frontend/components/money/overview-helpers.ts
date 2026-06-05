import type { TooltipProps, TooltipValueType } from 'recharts'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { formatCurrency, formatCurrencyWhole } from '@/lib/formatters'

export const allocationColors = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
]

export type MoneyOverviewSection =
  | 'decision'
  | 'allocation'
  | 'trend'
  | 'budget'
  | 'categories'
  | 'commitments'
  | 'levers'

export function formatMonthLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('en-US', {
    month: 'short',
    year: '2-digit',
  })
}

export function formatAssetGroup(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())
}

export function getTooltipNumber(
  value: TooltipValueType | undefined,
): number | null {
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

export function formatThousandsAxis(value: number) {
  return `$${Math.round(value / 1000)}k`
}

export const currencyTooltipFormatter: TooltipProps<TooltipValueType>['formatter'] =
  (value) =>
    formatCurrency(getTooltipNumber(value), { decimals: 0, nullDisplay: '—' })

export const monthTooltipLabelFormatter: TooltipProps<TooltipValueType>['labelFormatter'] =
  (label) =>
    formatMonthLabel(typeof label === 'string' ? label : String(label ?? ''))

export function signedCurrency(
  value: number | null | undefined,
  opts?: { decimals?: number },
) {
  const decimals = opts?.decimals ?? 0
  if (value == null) {
    return '—'
  }
  if (value === 0) {
    return formatCurrency(0, { decimals })
  }
  return `${value > 0 ? '+' : '-'}${formatCurrency(Math.abs(value), { decimals })}`
}

export function paceBadgeVariant(status: string) {
  switch (status) {
    case 'on_track':
    case 'under_plan':
    case 'upcoming':
      return 'success' as const
    case 'due_soon':
    case 'running_hot':
      return 'warning' as const
    case 'overdue':
    case 'essentials_above_plan':
    case 'discretionary_above_plan':
      return 'error' as const
    default:
      return 'secondary' as const
  }
}

export function comparisonBadgeVariant(change: number) {
  if (change > 0) {
    return 'warning' as const
  }
  if (change < 0) {
    return 'success' as const
  }
  return 'secondary' as const
}

export function priceInsightBadgeVariant(signalType: string) {
  switch (signalType) {
    case 'shrinkflation':
      return 'error' as const
    case 'unit_price_up':
    case 'price_up':
      return 'warning' as const
    case 'price_down':
      return 'success' as const
    default:
      return 'secondary' as const
  }
}

export function priceInsightBadgeLabel(signalType: string) {
  switch (signalType) {
    case 'shrinkflation':
      return 'Less product'
    case 'unit_price_up':
      return 'Unit price up'
    case 'price_up':
      return 'Price up'
    case 'price_down':
      return 'Price down'
    default:
      return 'Price move'
  }
}

export function latestCompletedMonthComparison(
  trend: HouseholdFinanceDashboard['reports']['monthlySpendTrend'],
) {
  if (trend.length < 2) {
    return null
  }

  const sorted = trend
    .slice()
    .sort((left, right) => left.month.localeCompare(right.month))
  const currentMonthKey = new Date().toISOString().slice(0, 7)
  const completed =
    sorted[sorted.length - 1]?.month === currentMonthKey
      ? sorted.slice(0, -1)
      : sorted

  if (completed.length < 2) {
    return null
  }

  const latest = completed[completed.length - 1]
  const previous = completed[completed.length - 2]
  const change = latest.totalSpend - previous.totalSpend
  const changePct =
    previous.totalSpend > 0 ? (change / previous.totalSpend) * 100 : null

  return { latest, previous, change, changePct }
}

export function decisionBadgeVariant(status: string) {
  switch (status) {
    case 'safe':
    case 'inside_guardrails':
    case 'needs_leading':
      return 'success' as const
    case 'tight':
    case 'review':
    case 'mixed':
    case 'partial_plan':
    case 'wants_leading':
      return 'warning' as const
    case 'hold':
    case 'wants_driving_gap':
    case 'essentials_driving_gap':
      return 'error' as const
    default:
      return 'secondary' as const
  }
}

export function formatCategoryPreview(
  categories: HouseholdFinanceDashboard['reports']['categoryBreakdown'],
) {
  if (categories.length === 0) {
    return 'No category split yet.'
  }
  return categories
    .slice(0, 2)
    .map(
      (category) =>
        `${category.category} ${formatCurrencyWhole(category.monthlyAverage)}`,
    )
    .join(' · ')
}

export function normalizeTrustStatus(status: string) {
  switch (status) {
    case 'trusted':
      return 'current'
    case 'partial':
    case 'review':
      return 'estimated'
    case 'blocked':
      return 'unavailable'
    default:
      return status
  }
}

export function trustCardValue(
  status: string,
  visibleValue: string,
  unavailableValue = '—',
) {
  return normalizeTrustStatus(status) === 'unavailable'
    ? unavailableValue
    : visibleValue
}

export function trustStatusLabel(status: string) {
  if (status === 'review') {
    return 'Review'
  }
  switch (normalizeTrustStatus(status)) {
    case 'current':
      return 'Current'
    case 'estimated':
      return 'Estimate'
    case 'known':
      return 'Known'
    case 'stale':
      return 'Stale'
    default:
      return 'Unavailable'
  }
}

export function trustBadgeVariant(status: string) {
  if (status === 'review') {
    return 'warning' as const
  }
  switch (normalizeTrustStatus(status)) {
    case 'current':
      return 'success' as const
    case 'estimated':
      return 'warning' as const
    case 'known':
      return 'secondary' as const
    case 'stale':
      return 'secondary' as const
    default:
      return 'outline' as const
  }
}
