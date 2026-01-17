/**
 * Shared formatting utilities for backtest components.
 * Centralizes value formatting to avoid duplication across BacktestDetails and related components.
 */

/**
 * Format a numeric value as a percentage with sign prefix.
 * Returns null-safe formatting.
 */
export function formatPercentValue(
  value: string | number | null | undefined,
): string {
  if (value === null || value === undefined) return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (Number.isNaN(num)) return '—'
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`
}

/**
 * Format a numeric value as USD currency.
 * Returns null-safe formatting.
 */
export function formatCurrencyValue(
  value: string | number | null | undefined,
): string {
  if (value === null || value === undefined) return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (Number.isNaN(num)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num)
}

/**
 * Format a number with fixed decimal places.
 * Returns null-safe formatting.
 */
export function formatNumber(
  value: string | number | null | undefined,
  decimals = 2,
): string {
  if (value === null || value === undefined) return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (Number.isNaN(num)) return '—'
  return num.toFixed(decimals)
}

/**
 * Parse a value to number, returning null if invalid.
 * Useful for converting API responses that may be string or number.
 */
export function parseToNumber(
  value: string | number | null | undefined,
): number | null {
  if (value === null || value === undefined) return null
  const num = typeof value === 'string' ? parseFloat(value) : value
  return Number.isNaN(num) ? null : num
}

/**
 * Get CSS class for value coloring based on positive/negative.
 */
export function getValueColorClass(
  value: number | null | undefined,
  positive = true,
): string {
  if (value === null || value === undefined) return 'text-text-muted'
  const isPositive = positive ? value >= 0 : value < 0
  return isPositive ? 'text-gain' : 'text-loss'
}
