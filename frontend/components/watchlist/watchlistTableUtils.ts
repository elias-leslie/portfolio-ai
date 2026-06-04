// Utility functions for WatchlistTable

export interface WatchlistPriceSnapshot {
  priceLabel: string
  changeLabel: string | null
  isPositiveChange: boolean
  freshnessLabel: string | null
  fromQuote: boolean
}

// Format pillar status
export function formatPillarStatus(status: string): string {
  const statusMap: Record<string, string> = {
    complete: '✓ Complete',
    partial: '◐ Partial',
    stale: '⏱ Stale',
    'n/a': '— N/A',
  }
  return statusMap[status] || status
}

// Get timezone abbreviation (EST, PST, etc.)
export function getTimezoneAbbreviation(timezone: string): string {
  const date = new Date()
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    timeZoneName: 'short',
  })
  const parts = formatter.formatToParts(date)
  const timeZonePart = parts.find((part) => part.type === 'timeZoneName')
  return timeZonePart?.value ?? ''
}

// Format date with timezone
export function formatDate(dateStr: string, timezone: string): string {
  const date = new Date(dateStr)
  const formatted = date.toLocaleString('en-US', {
    timeZone: timezone,
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
  const tzAbbr = getTimezoneAbbreviation(timezone)
  return `${formatted} ${tzAbbr}`
}

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }

  return null
}

export function getWatchlistPriceSnapshot(
  metadata?: Record<string, unknown>,
  quote?: { price?: number | null; freshnessLabel?: string | null } | null,
): WatchlistPriceSnapshot | null {
  if (!metadata && !quote) {
    return null
  }

  const quotePrice = toFiniteNumber(quote?.price)
  const fromQuote = quotePrice !== null
  const rawPrice = fromQuote ? quotePrice : metadata?.price
  const numericPrice = toFiniteNumber(rawPrice)
  const priceLabel =
    numericPrice !== null
      ? `$${numericPrice.toFixed(2)}`
      : typeof rawPrice === 'string' && rawPrice.trim()
        ? `$${rawPrice.trim()}`
        : null

  if (!priceLabel) {
    return null
  }

  const rawChange = fromQuote ? null : metadata?.rawChangePct
  const numericChange = toFiniteNumber(rawChange)
  const changeLabel =
    numericChange !== null
      ? `${numericChange >= 0 ? '+' : ''}${numericChange.toFixed(2)}%`
      : typeof rawChange === 'string' && rawChange.trim()
        ? rawChange.trim().endsWith('%')
          ? rawChange.trim()
          : `${rawChange.trim()}%`
        : null

  return {
    priceLabel,
    changeLabel,
    freshnessLabel: fromQuote ? (quote?.freshnessLabel ?? null) : null,
    fromQuote,
    isPositiveChange:
      numericChange !== null
        ? numericChange >= 0
        : !String(rawChange).trim().startsWith('-'),
  }
}
