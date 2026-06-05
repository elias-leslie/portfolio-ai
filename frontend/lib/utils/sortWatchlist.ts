import type { WatchlistItem } from '@/lib/api/watchlist'

export type SortField =
  | 'symbol'
  | 'overall'
  | 'price'
  | 'technical'
  | 'news'
  | 'updated'
  | 'signal'
  | 'risk'
export type SortDirection = 'asc' | 'desc'

// Rank maps so signal/risk sort by conviction/severity rather than alphabetically.
// Higher rank = stronger buy / higher risk; missing values sort to 0 (bottom in asc).
const SIGNAL_RANK: Record<string, number> = { BUY: 3, HOLD: 2, AVOID: 1 }
const RISK_RANK: Record<string, number> = {
  Low: 1,
  'Medium-Low': 2,
  Medium: 3,
  High: 4,
}

/**
 * Sort watchlist items by the specified field and direction.
 */
export function sortWatchlistItems(
  items: WatchlistItem[],
  field: SortField,
  direction: SortDirection,
): WatchlistItem[] {
  return [...items].sort((a, b) => {
    let aVal: string | number = ''
    let bVal: string | number = ''

    switch (field) {
      case 'symbol':
        aVal = a.symbol
        bVal = b.symbol
        break
      case 'overall':
        aVal = a.currentScore?.overall ?? -1
        bVal = b.currentScore?.overall ?? -1
        break
      case 'price':
        aVal = a.currentScore?.price.score ?? -1
        bVal = b.currentScore?.price.score ?? -1
        break
      case 'technical':
        aVal = a.currentScore?.technical.score ?? -1
        bVal = b.currentScore?.technical.score ?? -1
        break
      case 'news':
        aVal = a.newsSentimentScore ?? -2
        bVal = b.newsSentimentScore ?? -2
        break
      case 'signal':
        aVal = a.signalType ? (SIGNAL_RANK[a.signalType] ?? 0) : 0
        bVal = b.signalType ? (SIGNAL_RANK[b.signalType] ?? 0) : 0
        break
      case 'risk':
        aVal = a.riskLevel ? (RISK_RANK[a.riskLevel] ?? 0) : 0
        bVal = b.riskLevel ? (RISK_RANK[b.riskLevel] ?? 0) : 0
        break
      case 'updated':
        aVal = a.currentScore?.price?.updatedAt ?? a.updatedAt
        bVal = b.currentScore?.price?.updatedAt ?? b.updatedAt
        break
    }

    if (typeof aVal === 'string' && typeof bVal === 'string') {
      return direction === 'asc'
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal)
    }

    return direction === 'asc'
      ? (aVal as number) - (bVal as number)
      : (bVal as number) - (aVal as number)
  })
}
