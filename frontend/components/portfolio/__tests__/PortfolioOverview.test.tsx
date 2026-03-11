import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  usePortfolio,
  usePortfolioAnalytics,
} from '@/lib/hooks/usePortfolio'
import { PortfolioOverview } from '../PortfolioOverview'

vi.mock('@/components/portfolio/AssetAllocation', () => ({
  AssetAllocation: () => <div>Asset Allocation</div>,
}))
vi.mock('@/components/portfolio/JennyOperatorPanel', () => ({
  JennyOperatorPanel: () => <div>Jenny Operator Panel</div>,
}))
vi.mock('@/components/portfolio/PortfolioCoachAlerts', () => ({
  PortfolioCoachAlerts: () => <div>Portfolio Coach Alerts</div>,
}))
vi.mock('@/components/portfolio/DiversificationScore', () => ({
  DiversificationScore: () => <div>Diversification Score</div>,
}))
vi.mock('@/components/portfolio/PortfolioStats', () => ({
  PortfolioStats: () => <div>Portfolio Stats</div>,
}))
vi.mock('@/components/portfolio/RiskProfile', () => ({
  RiskProfile: () => <div>Risk Profile</div>,
}))
vi.mock('@/components/portfolio/TopPerformers', () => ({
  TopPerformers: () => <div>Top Performers</div>,
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  usePortfolio: vi.fn(),
  usePortfolioAnalytics: vi.fn(),
}))

describe('PortfolioOverview', () => {
  beforeEach(() => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: {
        positions: [],
        cashBalanceTotal: 5000,
        totalValue: 25000,
        totalCostBasis: 22000,
        totalGain: 3000,
        totalGainPct: 13.6,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)
    vi.mocked(usePortfolioAnalytics).mockReturnValue({
      data: {
        portfolioValue: {
          totalValue: 25000,
          totalCostBasis: 22000,
          totalGain: 3000,
          totalGainPct: 13.6,
        },
        cashBalanceTotal: 5000,
        cashInclusiveTotalValue: 30000,
        portfolioBeta: 0.92,
        portfolioVolatility: 0.18,
        sharpeRatio: 1.1,
        concentration: {
          topHoldingPct: 40,
          top3Pct: 70,
          top10Pct: 100,
          herfindahlIndex: 0.21,
        },
        sectorExposure: {
          technology: 60,
        },
        riskProfile: null,
        diversificationScore: null,
        topPerformers: [],
        bottomPerformers: [],
        numPositions: 0,
        numSymbols: 0,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)
  })

  it('shows a combined fatal error state when both portfolio queries fail', () => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('portfolio down'),
      refetch: vi.fn(),
    } as never)
    vi.mocked(usePortfolioAnalytics).mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('analytics down'),
      refetch: vi.fn(),
    } as never)

    render(<PortfolioOverview />)

    expect(screen.getByText(/failed to load portfolio overview/i)).toBeInTheDocument()
  })

  it('keeps core balances visible when analytics fail', () => {
    vi.mocked(usePortfolioAnalytics).mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('analytics down'),
      refetch: vi.fn(),
    } as never)

    render(<PortfolioOverview />)

    expect(screen.getByText(/some portfolio signals are unavailable right now/i)).toBeInTheDocument()
    expect(screen.getByText(/\$25,000.00/)).toBeInTheDocument()
    expect(screen.getByText(/0 live positions/i)).toBeInTheDocument()
    expect(screen.getByText(/top-performer and allocation breakdowns are waiting on portfolio analytics/i)).toBeInTheDocument()
  })
})
