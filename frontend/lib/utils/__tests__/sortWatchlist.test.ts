import { describe, expect, it } from 'vitest'
import type { WatchlistItem } from '@/lib/api/watchlist'
import { sortWatchlistItems } from '../sortWatchlist'

function item(
  symbol: string,
  overrides: Partial<WatchlistItem> = {},
): WatchlistItem {
  return {
    id: symbol,
    symbol,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('sortWatchlistItems', () => {
  describe('signal', () => {
    const items = [
      item('A', { signalType: 'HOLD' }),
      item('B', { signalType: 'AVOID' }),
      item('C', { signalType: 'BUY' }),
      item('D'), // no signal
    ]

    it('descending puts BUY first and missing signals last', () => {
      const sorted = sortWatchlistItems(items, 'signal', 'desc')
      expect(sorted.map((i) => i.symbol)).toEqual(['C', 'A', 'B', 'D'])
    })

    it('ascending puts missing/AVOID first and BUY last', () => {
      const sorted = sortWatchlistItems(items, 'signal', 'asc')
      expect(sorted.map((i) => i.symbol)).toEqual(['D', 'B', 'A', 'C'])
    })
  })

  describe('risk', () => {
    const items = [
      item('A', { riskLevel: 'High' }),
      item('B', { riskLevel: 'Low' }),
      item('C', { riskLevel: 'Medium' }),
      item('D', { riskLevel: 'Medium-Low' }),
    ]

    it('ascending orders Low → High by severity, not alphabetically', () => {
      const sorted = sortWatchlistItems(items, 'risk', 'asc')
      expect(sorted.map((i) => i.symbol)).toEqual(['B', 'D', 'C', 'A'])
    })

    it('descending orders High → Low', () => {
      const sorted = sortWatchlistItems(items, 'risk', 'desc')
      expect(sorted.map((i) => i.symbol)).toEqual(['A', 'C', 'D', 'B'])
    })
  })
})
