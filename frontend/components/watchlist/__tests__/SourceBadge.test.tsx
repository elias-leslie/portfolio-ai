import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SourceBadge } from '../SourceBadge'

describe('SourceBadge', () => {
  it('formats known source names for display', () => {
    render(<SourceBadge source="yfinance" />)
    expect(screen.getByText('YFinance')).toBeInTheDocument()
  })

  it('passes through unknown source names unchanged', () => {
    render(<SourceBadge source="CustomSource" />)
    expect(screen.getByText('CustomSource')).toBeInTheDocument()
  })

  it('formats all known provider names', () => {
    const providers = [
      ['twelvedata', 'TwelveData'],
      ['fmp', 'FMP'],
      ['polygon', 'Polygon'],
      ['finnhub', 'Finnhub'],
      ['alphavantage', 'AlphaVantage'],
    ] as const

    for (const [input, expected] of providers) {
      const { unmount } = render(<SourceBadge source={input} />)
      expect(screen.getByText(expected)).toBeInTheDocument()
      unmount()
    }
  })
})
