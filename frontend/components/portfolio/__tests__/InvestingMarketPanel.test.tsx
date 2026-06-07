'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { InvestingMarketPanel } from '../InvestingMarketPanel'

const useMarketIntelligenceMock = vi.fn()
const useSectorHistoryMock = vi.fn()

vi.mock('@/lib/hooks/useMarketIntelligence', () => ({
  useMarketIntelligence: () => useMarketIntelligenceMock(),
  useSectorHistory: (days: number) => useSectorHistoryMock(days),
}))

vi.mock('@/components/market/MarketStatusBadge', () => ({
  MarketStatusBadge: () => <div>Market Status</div>,
}))

vi.mock('@/components/market/SentimentTrendChart', () => ({
  SentimentTrendChart: () => <div>Sentiment Trend</div>,
}))

vi.mock('@/components/market/IndicatorsTrendChart', () => ({
  IndicatorsTrendChart: () => <div>Indicators Trend</div>,
}))

vi.mock('@/components/market/OvernightLeanChart', () => ({
  OvernightLeanChart: () => <div>Overnight Lean Trend</div>,
}))

vi.mock('@/components/market/MacroRegimeDriversTrendChart', () => ({
  MacroRegimeDriversTrendChart: () => <div>Regime Drivers Trend</div>,
}))

vi.mock('@/components/market/SectorPerformanceChart', () => ({
  SectorPerformanceChart: ({
    timeframe,
    onTimeframeChange,
  }: {
    timeframe: string
    onTimeframeChange: (timeframe: '1Y') => void
  }) => (
    <div>
      <p>Sector Chart {timeframe}</p>
      <button type="button" onClick={() => onTimeframeChange('1Y')}>
        Switch to 1Y
      </button>
    </div>
  ),
}))

const yearlyHistory = {
  sectors: [
    { symbol: 'XLK', name: 'Technology', data: [], currentPct: 18.4 },
    {
      symbol: 'XLC',
      name: 'Communication Services',
      data: [],
      currentPct: 12.1,
    },
    { symbol: 'XLI', name: 'Industrials', data: [], currentPct: 9.2 },
    {
      symbol: 'XLY',
      name: 'Consumer Discretionary',
      data: [],
      currentPct: 5.5,
    },
    { symbol: 'XLV', name: 'Healthcare', data: [], currentPct: -2.2 },
    { symbol: 'XLE', name: 'Energy', data: [], currentPct: -8.6 },
  ],
  periodStart: '2025-04-10',
  periodEnd: '2026-04-10',
}

const monthlyHistory = {
  sectors: [
    { symbol: 'XLK', name: 'Technology', data: [], currentPct: 6.8 },
    { symbol: 'XLF', name: 'Financials', data: [], currentPct: 5.4 },
    { symbol: 'XLU', name: 'Utilities', data: [], currentPct: 4.3 },
    { symbol: 'XLP', name: 'Consumer Staples', data: [], currentPct: 1.1 },
    { symbol: 'XLI', name: 'Industrials', data: [], currentPct: -1.4 },
    { symbol: 'XLE', name: 'Energy', data: [], currentPct: -3.9 },
  ],
  periodStart: '2026-03-10',
  periodEnd: '2026-04-10',
}

describe('InvestingMarketPanel', () => {
  beforeEach(() => {
    useMarketIntelligenceMock.mockReturnValue({
      data: {
        narrative: 'Backdrop remains constructive.',
        lastUpdated: '2026-04-10T15:30:00Z',
        indicators: {
          putcall: {
            value: 0.86,
            changePct: null,
            label: 'Put/Call Ratio',
            shortLabel: 'P/C',
            tooltip: 'Context',
            signal: 'Neutral',
            emoji: '🟡',
            lastUpdated: '2026-04-10T00:00:00Z',
          },
        },
      },
    })
    useSectorHistoryMock.mockImplementation((days: number) => ({
      data: days === 30 ? monthlyHistory : yearlyHistory,
      isLoading: false,
      error: null,
    }))
  })

  it('propagates the selected timeframe to the sector performance chart', async () => {
    const user = userEvent.setup()
    render(<InvestingMarketPanel />)

    expect(screen.getByText('Sector Chart 1M')).toBeInTheDocument()
    expect(screen.getByText('Regime Drivers Trend')).toBeInTheDocument()
    expect(screen.getByText('Sentiment Trend')).toBeInTheDocument()
    expect(screen.getByText('Indicators Trend')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Switch to 1Y' }))

    expect(screen.getByText('Sector Chart 1Y')).toBeInTheDocument()
  })
})
