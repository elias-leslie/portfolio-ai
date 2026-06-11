'use client'

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { InvestingMarketPanel } from '../InvestingMarketPanel'

vi.mock('@/components/market/Sp500TrendChart', () => ({
  Sp500TrendChart: () => <div>S&P 500 Trend</div>,
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

describe('InvestingMarketPanel', () => {
  // The sector performance chart (and its timeframe toggle) now lives in the
  // Today rotation strip (LeadingLaggingStrip); this panel is the stack of
  // trend charts only.
  it('renders the market trend panels', () => {
    render(<InvestingMarketPanel />)

    expect(screen.getByText('S&P 500 Trend')).toBeInTheDocument()
    expect(screen.getByText('Regime Drivers Trend')).toBeInTheDocument()
    expect(screen.getByText('Sentiment Trend')).toBeInTheDocument()
    expect(screen.getByText('Indicators Trend')).toBeInTheDocument()
    expect(screen.getByText('Overnight Lean Trend')).toBeInTheDocument()
  })
})
