import { useEffect, useMemo, useState } from 'react'
import type { WatchlistItem } from '@/lib/api/watchlist'
import {
  getStoredFilter,
  RISK_FILTER_VALUES,
  SIGNAL_FILTER_VALUES,
  STYLE_FILTER_VALUES,
  type RiskFilter,
  type SignalFilter,
  type StyleFilter,
} from './watchlistFilters'

export interface WatchlistCounts {
  style: Record<string, number>
  signal: Record<string, number>
  risk: Record<string, number>
}

export interface UseWatchlistFiltersReturn {
  styleFilter: StyleFilter
  setStyleFilter: (value: StyleFilter) => void
  signalFilter: SignalFilter
  setSignalFilter: (value: SignalFilter) => void
  riskFilter: RiskFilter
  setRiskFilter: (value: RiskFilter) => void
  searchQuery: string
  setSearchQuery: (value: string) => void
  filteredItems: WatchlistItem[]
  counts: WatchlistCounts
  hasActiveFilters: boolean
  resetFilters: () => void
}

export function useWatchlistFilters(
  items: WatchlistItem[],
): UseWatchlistFiltersReturn {
  const [styleFilter, setStyleFilter] = useState<StyleFilter>(() =>
    getStoredFilter('watchlist-style-filter', STYLE_FILTER_VALUES, 'all'),
  )
  const [signalFilter, setSignalFilter] = useState<SignalFilter>(() =>
    getStoredFilter('watchlist-signal-filter', SIGNAL_FILTER_VALUES, 'all'),
  )
  const [riskFilter, setRiskFilter] = useState<RiskFilter>(() =>
    getStoredFilter('watchlist-risk-filter', RISK_FILTER_VALUES, 'all'),
  )
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    localStorage.setItem('watchlist-style-filter', styleFilter)
  }, [styleFilter])

  useEffect(() => {
    localStorage.setItem('watchlist-signal-filter', signalFilter)
  }, [signalFilter])

  useEffect(() => {
    localStorage.setItem('watchlist-risk-filter', riskFilter)
  }, [riskFilter])

  const filteredItems = useMemo(() => {
    let result = items

    if (styleFilter !== 'all') {
      result = result.filter((item) => item.recommendedStyle === styleFilter)
    }

    if (signalFilter !== 'all') {
      result = result.filter((item) => item.signalType === signalFilter)
    }

    if (riskFilter !== 'all') {
      result = result.filter((item) => item.riskLevel === riskFilter)
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim()
      result = result.filter(
        (item) =>
          item.symbol.toLowerCase().includes(query) ||
          item.note?.toLowerCase().includes(query) ||
          item.narrativeHeadline?.toLowerCase().includes(query) ||
          item.signalType?.toLowerCase().includes(query) ||
          item.recommendedStyle?.toLowerCase().includes(query),
      )
    }

    return result
  }, [items, styleFilter, signalFilter, riskFilter, searchQuery])

  const counts = useMemo<WatchlistCounts>(() => {
    const style: Record<string, number> = {}
    const signal: Record<string, number> = {}
    const risk: Record<string, number> = {}

    for (const item of items) {
      if (item.recommendedStyle) {
        style[item.recommendedStyle] = (style[item.recommendedStyle] || 0) + 1
      }
      if (item.signalType) {
        signal[item.signalType] = (signal[item.signalType] || 0) + 1
      }
      if (item.riskLevel) {
        risk[item.riskLevel] = (risk[item.riskLevel] || 0) + 1
      }
    }

    return { style, signal, risk }
  }, [items])

  const hasActiveFilters =
    styleFilter !== 'all' ||
    signalFilter !== 'all' ||
    riskFilter !== 'all' ||
    searchQuery.trim().length > 0

  const resetFilters = () => {
    setStyleFilter('all')
    setSignalFilter('all')
    setRiskFilter('all')
    setSearchQuery('')
  }

  return {
    styleFilter,
    setStyleFilter,
    signalFilter,
    setSignalFilter,
    riskFilter,
    setRiskFilter,
    searchQuery,
    setSearchQuery,
    filteredItems,
    counts,
    hasActiveFilters,
    resetFilters,
  }
}
