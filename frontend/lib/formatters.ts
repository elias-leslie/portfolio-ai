// ---------------------------------------------------------------------------
// Shared number / label formatters
// ---------------------------------------------------------------------------

const NULL_DISPLAY = '—'

const numberFormatCache = new Map<string, Intl.NumberFormat>()

/** Cached, pinned en-US Intl.NumberFormat (throws RangeError for bad codes). */
function cachedNumberFormat(
  options: Intl.NumberFormatOptions,
): Intl.NumberFormat {
  const key = JSON.stringify(options)
  let formatter = numberFormatCache.get(key)
  if (!formatter) {
    formatter = new Intl.NumberFormat('en-US', options)
    numberFormatCache.set(key, formatter)
  }
  return formatter
}

/** Collapse values that round to zero at `decimals` so they never render as "-0". */
function normalizeZero(value: number, decimals: number): number {
  const factor = 10 ** decimals
  return Math.round(Math.abs(value) * factor) === 0 ? 0 : value
}

/** Format a number as currency (USD by default). */
export function formatCurrency(
  value: number | null | undefined,
  opts?: { decimals?: number; nullDisplay?: string; currency?: string },
): string {
  const {
    decimals = 2,
    nullDisplay = NULL_DISPLAY,
    currency = 'USD',
  } = opts ?? {}
  if (value == null || !Number.isFinite(value)) return nullDisplay
  const amount = normalizeZero(value, decimals)
  try {
    return cachedNumberFormat({
      style: 'currency',
      currency,
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(amount)
  } catch (error) {
    if (!(error instanceof RangeError)) throw error
    // Unknown ISO code from a provider: keep the code visible beside the number.
    const number = cachedNumberFormat({
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(amount)
    return `${currency} ${number}`
  }
}

/** Shorthand for 0-decimal USD currency. */
export function formatCurrencyWhole(
  value: number | null | undefined,
  opts?: { nullDisplay?: string },
): string {
  return formatCurrency(value, {
    decimals: 0,
    nullDisplay: opts?.nullDisplay ?? '—',
  })
}

/** Format a number as a percentage string. */
export function formatPercent(
  value: number | null | undefined,
  opts?: { decimals?: number; sign?: boolean; nullDisplay?: string },
): string {
  const { decimals = 1, sign = false, nullDisplay = NULL_DISPLAY } = opts ?? {}
  if (value == null || !Number.isFinite(value)) return nullDisplay

  const amount = normalizeZero(value, decimals)
  const prefix = sign ? (amount >= 0 ? '+' : '') : ''
  return `${prefix}${amount.toFixed(decimals)}%`
}

/** Signed dollar format for PnL values. */
export function formatPnlDollars(
  value: number | null | undefined,
  opts?: { nullDisplay?: string },
): string {
  if (value == null || !Number.isFinite(value))
    return opts?.nullDisplay ?? NULL_DISPLAY
  const amount = normalizeZero(value, 2)
  const prefix = amount >= 0 ? '+' : '-'
  return `${prefix}${formatCurrency(Math.abs(amount))}`
}

/** Compact dollar axis tick: "$500", "$2k", "-$1.5k". */
export function formatThousandsAxis(value: number): string {
  if (!Number.isFinite(value)) return NULL_DISPLAY
  const sign = value < 0 ? '-' : ''
  const magnitude = Math.abs(value)
  if (magnitude < 1000) {
    const rounded = Math.round(magnitude)
    return rounded === 0 ? '$0' : `${sign}$${rounded}`
  }
  const thousands = magnitude / 1000
  const label = Number.isInteger(thousands)
    ? thousands.toFixed(0)
    : thousands.toFixed(1)
  return `${sign}$${label}k`
}

/** Format a whole number with locale grouping. */
export function formatInteger(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return NULL_DISPLAY
  return value.toLocaleString()
}

/** Format a number as hours (e.g. "3.2h"). */
export function formatHours(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return NULL_DISPLAY
  return `${value.toFixed(1)}h`
}

/** Format seconds into a human-friendly duration. */
export function formatSeconds(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return NULL_DISPLAY
  if (value >= 3600) return `${(value / 3600).toFixed(1)}h`
  if (value >= 60) return `${Math.round(value / 60)}m`
  return `${Math.round(value)}s`
}

/** Format a millisecond duration as zero-padded mm:ss (e.g. "03:07"). */
export function formatElapsed(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms)) return '—'
  const seconds = Math.floor(ms / 1000)
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
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
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}
