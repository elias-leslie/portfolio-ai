import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useRecommendations, useTrackInPortfolio } from '@/lib/hooks/useRecommendations'
import { TodayIdeasSection } from '../TodayIdeasSection'

vi.mock('@/components/recommendations/DecisionMemoCard', () => ({
  DecisionMemoCard: ({ recommendation }: { recommendation: { symbol: string } }) => (
    <div>{recommendation.symbol}</div>
  ),
}))
vi.mock('@/components/recommendations/TrackInPortfolioModal', () => ({
  TrackInPortfolioModal: () => null,
}))
vi.mock('@/lib/hooks/useRecommendations', () => ({
  useRecommendations: vi.fn(),
  useTrackInPortfolio: vi.fn(),
}))

const mockRecommendation = {
  symbol: 'VTI',
  strategyId: 's1',
  strategyName: 'Trend',
  strategyType: 'momentum',
  signalStrength: 8,
  signalType: 'BUY',
  signalReasons: ['Reason'],
  entryPrice: 100,
  currentPrice: 101,
  priceChangePct: 1,
  signalStatus: 'valid',
  stopLoss: 95,
  targetPrice: 110,
  positionSizeDollars: 5000,
  positionSizeShares: 49,
  riskRewardRatio: 2,
  expectedSharpe: null,
  signalDate: '2026-03-10',
  generatedAt: '2026-03-10T00:00:00Z',
  validationType: 'both',
}

describe('TodayIdeasSection', () => {
  beforeEach(() => {
    vi.mocked(useTrackInPortfolio).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as never)
  })

  it('shows summary context for the current recommendations set', () => {
    vi.mocked(useRecommendations).mockReturnValue({
      data: {
        total: 9,
        summary: {
          buySignals: 6,
          sellSignals: 2,
          holdSignals: 1,
          totalPositionSize: 12000,
          avgSignalStrength: 7.6,
          portfolioSize: 100000,
          positionPct: 0.05,
        },
        recommendations: [mockRecommendation],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)

    render(<TodayIdeasSection />)

    expect(screen.getByText(/showing 1 of 9 setups · average strength 7.6\/10 · 5% sizing rule/i)).toBeInTheDocument()
    expect(screen.getByText(/\$12,000/)).toBeInTheDocument()
    expect(screen.getByText('BUY 6')).toBeInTheDocument()
    expect(screen.getByText('HOLD 1')).toBeInTheDocument()
    expect(screen.getByText('SELL 2')).toBeInTheDocument()
  })

  it('shows a refresh hint when ideas are refetching in the background', () => {
    vi.mocked(useRecommendations).mockReturnValue({
      data: {
        total: 1,
        summary: {
          buySignals: 1,
          sellSignals: 0,
          holdSignals: 0,
          totalPositionSize: 5000,
          avgSignalStrength: 8,
          portfolioSize: 100000,
          positionPct: 0.05,
        },
        recommendations: [mockRecommendation],
      },
      isLoading: false,
      isFetching: true,
      error: null,
      refetch: vi.fn(),
    } as never)

    render(<TodayIdeasSection />)

    expect(screen.getByText(/refreshing ideas with the latest prices and strategy scores/i)).toBeInTheDocument()
  })

  it('does not show refresh hint when isFetching is false', () => {
    vi.mocked(useRecommendations).mockReturnValue({
      data: {
        total: 1,
        summary: {
          buySignals: 1,
          sellSignals: 0,
          holdSignals: 0,
          totalPositionSize: 5000,
          avgSignalStrength: 8,
          portfolioSize: 100000,
          positionPct: 0.05,
        },
        recommendations: [mockRecommendation],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)

    render(<TodayIdeasSection />)

    expect(screen.queryByText(/refreshing ideas with the latest prices and strategy scores/i)).not.toBeInTheDocument()
  })

  it('shows loading indicator when isLoading is true', () => {
    vi.mocked(useRecommendations).mockReturnValue({
      data: null,
      isLoading: true,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)

    render(<TodayIdeasSection />)

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows error UI when error is set', () => {
    const errorMessage = 'Failed to load recommendations'
    vi.mocked(useRecommendations).mockReturnValue({
      data: null,
      isLoading: false,
      isFetching: false,
      error: new Error(errorMessage),
      refetch: vi.fn(),
    } as never)

    render(<TodayIdeasSection />)

    expect(screen.getByText(/error|failed/i)).toBeInTheDocument()
  })
})
