import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PortfolioStats } from '../PortfolioStats'

describe('PortfolioStats', () => {
  const baseAnalytics = {
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
    bottomPerformers: [],
    numPositions: 5,
    numSymbols: 4,
  }

  it('uses the concentration metric for largest position and shows unique symbols', () => {
    render(
      <PortfolioStats
        analytics={{
          ...baseAnalytics,
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
        }}
      />,
    )

    expect(screen.getByText('Unique Symbols')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('22.5%')).toBeInTheDocument()
  })

  it('renders correctly with riskProfile: null', () => {
    render(
      <PortfolioStats
        analytics={{
          ...baseAnalytics,
          riskProfile: null,
          diversificationScore: { score: 0.75, level: 'good', numHoldings: 5, numSectors: 3 },
          topPerformers: [
            {
              symbol: 'MSFT',
              gainPct: 15,
              gainAmount: 1500,
              currentValue: 5000,
              weightPct: 10,
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('Portfolio Stats')).toBeInTheDocument()
    expect(screen.getByText('Total Positions')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('renders correctly with diversificationScore: null', () => {
    render(
      <PortfolioStats
        analytics={{
          ...baseAnalytics,
          riskProfile: { level: 'moderate', score: 50, factors: {} },
          diversificationScore: null,
          topPerformers: [
            {
              symbol: 'GOOGL',
              gainPct: 10,
              gainAmount: 1000,
              currentValue: 3000,
              weightPct: 6,
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('Portfolio Stats')).toBeInTheDocument()
    expect(screen.getByText('Unique Symbols')).toBeInTheDocument()
  })

  it('renders correctly with empty topPerformers array', () => {
    render(
      <PortfolioStats
        analytics={{
          ...baseAnalytics,
          riskProfile: { level: 'conservative', score: 30, factors: {} },
          diversificationScore: { score: 0.85, level: 'excellent', numHoldings: 8, numSectors: 5 },
          topPerformers: [],
        }}
      />,
    )

    expect(screen.getByText('Portfolio Stats')).toBeInTheDocument()
    expect(screen.getByText('Invested Value')).toBeInTheDocument()
    expect(screen.getByText('Cash Reserve')).toBeInTheDocument()
  })

  it('renders correctly when riskProfile, diversificationScore, and topPerformers are all null/empty', () => {
    render(
      <PortfolioStats
        analytics={{
          ...baseAnalytics,
          riskProfile: null,
          diversificationScore: null,
          topPerformers: [],
        }}
      />,
    )

    expect(screen.getByText('Portfolio Stats')).toBeInTheDocument()
    expect(screen.getByText('Total Positions')).toBeInTheDocument()
    expect(screen.getByText('Largest Position')).toBeInTheDocument()
    expect(screen.getByText('22.5%')).toBeInTheDocument()
  })
})
