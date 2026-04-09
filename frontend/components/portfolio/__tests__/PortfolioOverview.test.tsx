import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PortfolioAnalytics, PortfolioResponse } from '@/lib/api/portfolio'
import { usePortfolio, usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { PortfolioOverview } from '../PortfolioOverview'

// Helper to create properly typed portfolio mock
function createPortfolioMock(
  overrides?: Partial<ReturnType<typeof usePortfolio>>,
): ReturnType<typeof usePortfolio> {
  return {
    data: {
      positions: [],
      cashBalanceTotal: 5000,
      totalValue: 25000,
      totalCostBasis: 22000,
      totalGain: 3000,
      totalGainPct: 13.6,
    } as PortfolioResponse,
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof usePortfolio>
}

// Helper to create properly typed portfolio analytics mock
function createPortfolioAnalyticsMock(
  overrides?: Partial<ReturnType<typeof usePortfolioAnalytics>>,
): ReturnType<typeof usePortfolioAnalytics> {
  return {
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
    } as PortfolioAnalytics,
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof usePortfolioAnalytics>
}

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
    vi.mocked(usePortfolio).mockReturnValue(createPortfolioMock())
    vi.mocked(usePortfolioAnalytics).mockReturnValue(
      createPortfolioAnalyticsMock(),
    )
  })

  it('shows a combined fatal error state when both portfolio queries fail', () => {
    vi.mocked(usePortfolio).mockReturnValue(
      createPortfolioMock({
        data: undefined,
        error: new Error('portfolio down'),
      }),
    )
    vi.mocked(usePortfolioAnalytics).mockReturnValue(
      createPortfolioAnalyticsMock({
        data: undefined,
        error: new Error('analytics down'),
      }),
    )

    render(<PortfolioOverview />)

    expect(
      screen.getByText(/failed to load portfolio overview/i),
    ).toBeInTheDocument()
  })

  it('keeps core balances visible when analytics fail', () => {
    vi.mocked(usePortfolioAnalytics).mockReturnValue(
      createPortfolioAnalyticsMock({
        data: undefined,
        error: new Error('analytics down'),
      }),
    )

    render(<PortfolioOverview />)

    expect(
      screen.getByText(/some portfolio signals are unavailable right now/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/\$25,000.00/)).toBeInTheDocument()
    expect(screen.getByText(/0 live positions/i)).toBeInTheDocument()
    expect(
      screen.getByText(
        /top-performer and allocation breakdowns are waiting on portfolio analytics/i,
      ),
    ).toBeInTheDocument()
  })
})
