import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PortfolioStats } from '../PortfolioStats'

describe('PortfolioStats', () => {
  it('uses the concentration metric for largest position and shows unique symbols', () => {
    render(
      <PortfolioStats
        analytics={{
          portfolioValue: {
            totalValue: 50000,
            totalCostBasis: 42000,
            totalGain: 8000,
            totalGainPct: 19,
          },
          cashBalanceTotal: 10000,
          cashInclusiveTotalValue: 60000,
          portfolioBeta: 1.02,
          portfolioVolatility: 0.18,
          sharpeRatio: 1.2,
          concentration: {
            topHoldingPct: 22.5,
            top3Pct: 48,
            top10Pct: 100,
            herfindahlIndex: 0.14,
          },
          sectorExposure: {},
          riskProfile: null,
          diversificationScore: null,
          topPerformers: [
            {
              symbol: 'AAPL',
              gainPct: 12,
              gainAmount: 1200,
              currentValue: 4000,
              weightPct: 8,
            },
          ],
          bottomPerformers: [],
          numPositions: 5,
          numSymbols: 4,
        }}
      />,
    )

    expect(screen.getByText('Unique Symbols')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('22.5%')).toBeInTheDocument()
  })
})
