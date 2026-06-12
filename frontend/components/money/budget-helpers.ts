import type { TooltipProps, TooltipValueType } from 'recharts'
import { formatCurrency } from '@/lib/formatters'

export type BudgetWindow = '1m' | '3m' | '6m'

export const budgetWindows: Array<{ value: BudgetWindow; label: string }> = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
]

export const trendColors = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
  'var(--color-chart-blue)',
  'var(--color-chart-cyan)',
  'var(--color-chart-orange)',
]

/**
 * Classify a category's cap status from its confirmed and suggested caps versus
 * actual spend. Pure so the badge label/variant can be unit-tested without the
 * panel. A confirmed cap always wins over a suggested one.
 */
export function budgetStatus(
  currentBudget: number | null,
  foundBudget: number | null,
  actual: number,
) {
  if (currentBudget != null) {
    return {
      label: actual > currentBudget ? 'Over confirmed cap' : 'Confirmed cap',
      variant:
        actual > currentBudget ? ('warning' as const) : ('success' as const),
    }
  }
  if (foundBudget != null) {
    return {
      label: actual > foundBudget ? 'Over suggested cap' : 'Suggested cap',
      variant:
        actual > foundBudget ? ('warning' as const) : ('outline' as const),
    }
  }
  return {
    label: 'No cap yet',
    variant: 'secondary' as const,
  }
}

export function formatBudgetDate(value: string) {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

export function formatMonthLabel(value: string) {
  const date = new Date(`${value}-01T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('en-US', {
    month: 'short',
    year: '2-digit',
  })
}

export function formatThousandsAxis(value: number) {
  if (Math.abs(value) < 1000) {
    return `$${Math.round(value)}`
  }
  const thousands = value / 1000
  return `$${Number.isInteger(thousands) ? thousands.toFixed(0) : thousands.toFixed(1)}k`
}

export function tooltipNumber(
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

export const currencyTooltipFormatter: TooltipProps<TooltipValueType>['formatter'] =
  (value, name) => [
    formatCurrency(tooltipNumber(value), { decimals: 0, nullDisplay: '—' }),
    String(name),
  ]

export const monthTooltipLabelFormatter: TooltipProps<TooltipValueType>['labelFormatter'] =
  (label) =>
    formatMonthLabel(typeof label === 'string' ? label : String(label ?? ''))

export function trendKey(category: string, index: number) {
  const slug = category
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return `category_${slug || 'unknown'}_${index}`
}
