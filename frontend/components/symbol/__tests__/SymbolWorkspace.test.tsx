import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useJennyDashboard } from '@/lib/hooks/usePortfolio'
import { useSymbolIntelligence } from '@/lib/hooks/useSymbolIntelligence'
import { SymbolWorkspace } from '../SymbolWorkspace'

vi.mock('@/components/symbol/SymbolWorkflowPanel', () => ({
  SymbolWorkflowPanel: () => <div>Workflow Panel</div>,
}))
vi.mock('@/components/watchlist/ThesisSection', () => ({
  ThesisSection: () => <div>Thesis Section</div>,
}))
vi.mock('@/lib/hooks/useSymbolIntelligence', () => ({
  useSymbolIntelligence: vi.fn(),
}))
vi.mock('@/lib/hooks/usePortfolio', () => ({
  useJennyDashboard: vi.fn(),
}))
vi.mock('@/lib/hooks/usePreferences', () => ({
  usePreferences: () => ({ data: undefined, isLoading: false }),
}))

describe('SymbolWorkspace', () => {
  beforeEach(() => {
    vi.mocked(useSymbolIntelligence).mockReturnValue({
      data: {
        symbol: 'VTI',
        generatedAt: '2026-03-10T15:30:00Z',
        scores: { overall: 78, signalType: 'BUY', signalStrength: 7, pillars: {} },
        signal: { type: 'BUY', strength: 7, confirmations: 3, avoidFlags: 0 },
        trading: {
          style: 'swing',
          confidence: 7,
          holdingPeriod: 'weeks',
          riskLevel: 'medium',
          entryPrice: 280,
          stopLoss: 265,
          profitTarget: 310,
          positionSizeShares: 12,
          positionSizeDollars: 3360,
        },
        portfolio: {
          held: false,
          position: null,
          context: {
            totalValue: 200000,
            numHoldings: 8,
            diversificationScore: 74,
            sectorWeight: 12,
            concentrationTop3: 28,
          },
        },
        news: {
          sentimentLabel: 'Constructive',
          sentimentScore: 0.7,
          articleCount24H: 4,
          headline: 'Balanced setup',
          keyEvents: [],
          recentArticles: [
            {
              headline: 'ETF flows remain constructive',
              source: 'Reuters',
              publishedAt: '2026-03-10T14:00:00Z',
            },
          ],
        },
        market: {
          fearGreedLabel: 'Neutral',
          fearGreedScore: 55,
          vix: 18.2,
        },
        alerts: [{ icon: 'alert', label: 'Watch closely', priority: 1 }],
        recommendation: {
          action: 'hold_for_breakout',
          reasoning: [],
          ifNotHeld: {
            action: 'avoid',
            reasoning: 'Signal: HOLD, Strength: 2/10',
            sizePct: 1,
          },
        },
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)
    vi.mocked(useJennyDashboard).mockReturnValue({
      data: {
        routines: [],
        notifications: [],
        symbolReviews: [],
        tradeReviews: [],
        scorecards: [],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)
  })

  it('shows generated-at telemetry, article context, and decision fallback copy', async () => {
    const user = userEvent.setup()
    render(<SymbolWorkspace symbol="vti" />)

    expect(screen.getByText(/1 alert · 1 recent article · 4 articles in 24h · 3 green lights · 0 caution flags/i)).toBeInTheDocument()
    expect(screen.getByText(/current setup: buy · confidence 7\/10/i)).toBeInTheDocument()
    expect(screen.getByText(/8 holdings · top 3 holdings make up 28.0% · diversification score 74/i)).toBeInTheDocument()
    expect(screen.getByText(/7\/10 confidence · medium/i)).toBeInTheDocument()
    expect(screen.getByText(/if you do not own it yet: avoid · current setup: hold · confidence 2\/10 · starter size 1.0%/i)).toBeInTheDocument()
    expect(screen.getByText(/no decision memo reasoning is available yet/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Market' }))

    expect(screen.getByText(/recent articles/i)).toBeInTheDocument()
    expect(screen.getByText(/etf flows remain constructive/i)).toBeInTheDocument()
    expect(screen.getByText(/constructive · score 0.7 · 4 articles in the last 24h/i)).toBeInTheDocument()
  })

  it('shows a Jenny warning when review data is unavailable', () => {
    vi.mocked(useJennyDashboard).mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('jenny unavailable'),
      refetch: vi.fn(),
    } as never)

    render(<SymbolWorkspace symbol="vti" />)

    expect(screen.getByText(/jenny review data is temporarily unavailable/i)).toBeInTheDocument()
  })

  it('marks the refresh control busy while symbol intelligence is refetching', () => {
    vi.mocked(useSymbolIntelligence).mockReturnValue({
      data: {
        symbol: 'VTI',
        generatedAt: '2026-03-10T15:30:00Z',
        scores: { overall: 78, signalType: 'BUY', signalStrength: 7, pillars: {} },
        signal: { type: 'BUY', strength: 7, confirmations: 0, avoidFlags: 0 },
        trading: null,
        portfolio: { held: false, position: null, context: null },
        news: {
          articleCount24H: 0,
          headline: 'Balanced setup',
          keyEvents: [],
          recentArticles: [],
        },
        market: {
          fearGreedLabel: 'Neutral',
          fearGreedScore: 55,
          vix: 18.2,
        },
        alerts: [],
        recommendation: {
          action: 'watch',
          reasoning: ['Wait.'],
          ifNotHeld: null,
        },
      },
      isLoading: false,
      isFetching: true,
      error: null,
      refetch: vi.fn(),
    } as never)

    render(<SymbolWorkspace symbol="vti" />)

    expect(screen.getByRole('button', { name: 'Refresh' })).toHaveAttribute('aria-busy', 'true')
  })
})
