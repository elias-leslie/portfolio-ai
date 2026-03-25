// ---------------------------------------------------------------------------
// Shared number / label formatters
// ---------------------------------------------------------------------------

/** Format a number as USD currency. */
export function formatCurrency(
  value: number | null | undefined,
  opts?: { decimals?: number; nullDisplay?: string },
): string {
  const { decimals = 2, nullDisplay = '—' } = opts ?? {}
  if (value == null) return nullDisplay

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/** Shorthand for 0-decimal USD currency. */
export function formatCurrencyWhole(
  value: number | null | undefined,
  opts?: { nullDisplay?: string },
): string {
  return formatCurrency(value, { decimals: 0, nullDisplay: opts?.nullDisplay ?? '—' })
}

/** Format a number as a percentage string. */
export function formatPercent(
  value: number | null | undefined,
  opts?: { decimals?: number; sign?: boolean; nullDisplay?: string },
): string {
  const { decimals = 1, sign = false, nullDisplay = '—' } = opts ?? {}
  if (value == null) return nullDisplay

  const prefix = sign ? (value >= 0 ? '+' : '') : ''
  return `${prefix}${value.toFixed(decimals)}%`
}

/** Signed dollar format for PnL values. */
export function formatPnlDollars(
  value: number | null | undefined,
  opts?: { nullDisplay?: string },
): string {
  if (value == null) return opts?.nullDisplay ?? '—'
  const prefix = value >= 0 ? '+$' : '-$'
  return `${prefix}${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

/** Format a whole number with locale grouping. */
export function formatInteger(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString()
}

/** Format a number as hours (e.g. "3.2h"). */
export function formatHours(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value.toFixed(1)}h`
}

/** Format seconds into a human-friendly duration. */
export function formatSeconds(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 3600) return `${(value / 3600).toFixed(1)}h`
  if (value >= 60) return `${Math.round(value / 60)}m`
  return `${Math.round(value)}s`
}

/** Convert an enum-style string to a human label (e.g. "my_value" → "My value"). */
export function formatEnumLabel(
  value: string | null | undefined,
  fallback = 'Awaiting review',
): string {
  if (!value) return fallback
  const words = value.replaceAll('_', ' ').toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** Format bytes into a human-readable file size. */
export function formatFileSize(bytes: number): string {
  if (bytes <= 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}
