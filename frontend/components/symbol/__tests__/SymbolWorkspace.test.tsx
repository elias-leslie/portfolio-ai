import { render, screen, within } from '@testing-library/react'
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
    vi.clearAllMocks()
    window.history.replaceState(null, '', '/')

    vi.mocked(useSymbolIntelligence).mockReturnValue({
      data: {
        symbol: 'VTI',
        generatedAt: '2026-03-10T15:30:00Z',
        scores: {
          overall: 78,
          signalType: 'BUY',
          signalStrength: 7,
          pillars: {},
        },
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
          held: true,
          position: {
            shares: 8,
            costBasis: 201,
            currentValue: 1634.42,
            gain: 22.75,
            gainPct: 1.4,
            weightPct: 0.2,
          },
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
        decision: {
          action: 'hold_for_breakout',
          headline: 'Hold for breakout',
          summary: 'No live recommendation summary is available yet.',
          reasoning: [],
          sourceKind: 'live_signal_model',
          sourceLabel: 'Live signal model',
          sourceTimestamp: '2026-03-10T15:30:00Z',
          severity: null,
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
        symbolReviews: [
          {
            symbol: 'VTI',
            finalVerdict: 'hold',
            averageConfidence: 0.7,
            thesisStatus: null,
            thesisAction: null,
            managementAction: 'hold',
            managementDetail:
              'Older review said VTI was up 31.1% and 39.2% of the portfolio.',
            positionGainPct: 31.1,
            positionWeightPct: 39.2,
            reasons: ['Older position facts should not compete with the alert.'],
            evaluations: [],
          },
        ],
        tradeReviews: [],
        scorecards: [],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)
  })

  it('shows live-model decisions clearly and keeps portfolio context honest', async () => {
    const user = userEvent.setup()
    render(<SymbolWorkspace symbol="vti" />)

    expect(screen.getByText(/1 alert/i)).toBeInTheDocument()
    expect(
      screen.getByText(/score 78 · buy · strength 7\/10/i),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/live signal model/i).length).toBeGreaterThan(0)
    expect(
      screen.getAllByText(/8 shares · \+1.4% · 0.2% of invested assets/i)
        .length,
    ).toBeGreaterThan(0)
    expect(
      screen.queryByText(/\+0.2% of invested assets/i),
    ).not.toBeInTheDocument()
    expect(
      screen.getAllByText(
        /invested portfolio has 8 holdings · top 3 invested holdings make up 28.0% · diversification score 74/i,
      ).length,
    ).toBeGreaterThan(0)
    expect(screen.getByText(/invested weight/i)).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /review concentration in holdings/i }),
    ).toHaveAttribute(
      'href',
      '/portfolio?tab=holdings&highlight=concentration#portfolio-overview',
    )
    expect(screen.getByText(/7\/10 confidence · medium/i)).toBeInTheDocument()
    expect(
      screen.queryByText(/if you do not own it yet/i),
    ).not.toBeInTheDocument()
    expect(
      screen.getByText(
        /no jenny\/data reasoning is attached to this decision yet/i,
      ),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Track' }))

    expect(screen.getByText(/recent articles/i)).toBeInTheDocument()
    expect(
      screen.getByText(/etf flows remain constructive/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        /constructive · score 0.7 · 4 articles in the last 24h/i,
      ),
    ).toBeInTheDocument()
  })

  it('prioritizes active Jenny alerts and omits placeholder metrics when data is missing', async () => {
    const user = userEvent.setup()
    vi.mocked(useSymbolIntelligence).mockReturnValue({
      data: {
        symbol: 'VTI',
        generatedAt: '2026-03-10T15:30:00Z',
        scores: {
          overall: 68,
          signalType: 'BUY',
          signalStrength: 7,
          pillars: {},
        },
        signal: {
          type: 'BUY',
          strength: 7,
          confirmations: null,
          avoidFlags: 0,
        },
        trading: null,
        portfolio: {
          held: true,
          position: {
            shares: 8,
            costBasis: 201,
            currentValue: 1634.42,
            gain: 22.75,
            gainPct: 1.4,
            weightPct: 0.2,
          },
          context: {
            totalValue: 200000,
            numHoldings: 8,
            diversificationScore: null,
            sectorWeight: null,
            concentrationTop3: null,
          },
        },
        news: {
          articleCount24H: 0,
          headline: 'Setup changed',
          keyEvents: [],
          recentArticles: [],
        },
        market: {
          fearGreedLabel: 'Fear',
          fearGreedScore: 28,
          vix: 25.8,
        },
        alerts: [],
        recommendation: {
          action: 'buy_more',
          reasoning: ['Strong BUY signal (7/10)'],
          ifNotHeld: null,
        },
        decision: {
          action: 'position_exit',
          headline: 'Exit this position',
          summary: 'Reduce risk now.',
          reasoning: [
            'The position no longer fits the thesis.',
            'Reduce risk now.',
          ],
          sourceKind: 'jenny_alert',
          sourceLabel: 'Jenny alert',
          sourceTimestamp: '2026-03-10T16:00:00Z',
          severity: 'critical',
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
        notifications: [
          {
            id: 'note-1',
            routineId: 'routine-1',
            symbol: 'VTI',
            category: 'position_exit',
            severity: 'critical',
            status: 'open',
            title: 'VTI: Exit this position',
            detail: 'The position no longer fits the thesis.',
            recommendation: 'Reduce risk now.',
            createdAt: '2026-03-10T16:00:00Z',
            acknowledgedAt: null,
            metadata: {},
          },
        ],
        symbolReviews: [
          {
            symbol: 'VTI',
            finalVerdict: 'hold',
            averageConfidence: 0.7,
            thesisStatus: null,
            thesisAction: null,
            managementAction: 'hold',
            managementDetail:
              'Older review said VTI was up 31.1% and 39.2% of the portfolio.',
            positionGainPct: 31.1,
            positionWeightPct: 39.2,
            reasons: ['Older position facts should not compete with the alert.'],
            evaluations: [],
          },
        ],
        tradeReviews: [],
        scorecards: [],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)

    render(<SymbolWorkspace symbol="vti" />)

    expect(screen.getAllByText(/exit this position/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/reduce risk now\./i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/jenny alert · critical/i).length).toBeGreaterThan(
      0,
    )
    expect(screen.getByText(/signal disagreement/i)).toBeInTheDocument()
    expect(screen.getByText(/live setup evidence/i)).toBeInTheDocument()
    expect(screen.getByText(/buy more/i)).toBeInTheDocument()
    expect(screen.getAllByText(/current decision/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/1 alert/i)).toBeInTheDocument()
    expect(screen.queryByText(/live signal model/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/0 recent article/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/0 green lights/i)).not.toBeInTheDocument()
    expect(
      screen.getAllByText(/invested portfolio has 8 holdings/i).length,
    ).toBeGreaterThan(0)
    expect(
      screen.queryByText(/top 3 invested holdings make up/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/diversification score/i)).not.toBeInTheDocument()
    const historicalReview = screen
      .getByText(/previous jenny review: hold/i)
      .closest('details')
    expect(historicalReview).not.toHaveAttribute('open')
    expect(screen.getByRole('button', { name: 'Track' }).textContent).toBe(
      'Track1',
    )

    await user.click(screen.getByRole('button', { name: 'Track' }))

    const newsAndAlerts = screen.getByText(/news and alerts/i).closest('section')
    expect(newsAndAlerts).not.toBeNull()
    expect(
      within(newsAndAlerts as HTMLElement).getByText(/current jenny alert/i),
    ).toBeInTheDocument()
    expect(
      within(newsAndAlerts as HTMLElement).getByText(/vti: exit this position/i),
    ).toBeInTheDocument()
  })

  it('explains when only aggregate news volume is available', async () => {
    const user = userEvent.setup()

    vi.mocked(useSymbolIntelligence).mockReturnValue({
      data: {
        symbol: 'NVDA',
        generatedAt: '2026-03-10T15:30:00Z',
        scores: {
          overall: 67,
          signalType: 'BUY',
          signalStrength: 7,
          pillars: {},
        },
        signal: {
          type: 'BUY',
          strength: 7,
          confirmations: null,
          avoidFlags: 0,
        },
        trading: null,
        portfolio: { held: false, position: null, context: null },
        news: {
          sentimentLabel: null,
          sentimentScore: 0.1,
          articleCount24H: 200,
          headline: null,
          keyEvents: [],
          recentArticles: [],
        },
        market: {
          fearGreedLabel: 'Fear',
          fearGreedScore: 28,
          vix: 25.8,
        },
        alerts: [],
        recommendation: {
          action: 'buy_more',
          reasoning: ['Strong BUY signal (7/10)'],
          ifNotHeld: null,
        },
        decision: {
          action: 'buy_more',
          headline: 'Buy more',
          summary: 'Strong BUY signal (7/10)',
          reasoning: ['Strong BUY signal (7/10)'],
          sourceKind: 'live_signal_model',
          sourceLabel: 'Live signal model',
          sourceTimestamp: '2026-03-10T15:30:00Z',
          severity: null,
        },
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)

    render(<SymbolWorkspace symbol="nvda" />)

    await user.click(screen.getByRole('button', { name: 'Track' }))

    expect(
      screen.getByText(
        /article volume is available, but recent headlines were not attached to this snapshot/i,
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/sentiment score 0.1 · 200 articles in the last 24h/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        /article volume is available, but this snapshot did not attach recent headlines yet/i,
      ),
    ).toBeInTheDocument()
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

    expect(
      screen.getByText(/jenny review data is temporarily unavailable/i),
    ).toBeInTheDocument()
  })

  it('marks the refresh control busy while symbol intelligence is refetching', () => {
    vi.mocked(useSymbolIntelligence).mockReturnValue({
      data: {
        symbol: 'VTI',
        generatedAt: '2026-03-10T15:30:00Z',
        scores: {
          overall: 78,
          signalType: 'BUY',
          signalStrength: 7,
          pillars: {},
        },
        signal: {
          type: 'BUY',
          strength: 7,
          confirmations: null,
          avoidFlags: 0,
        },
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
        decision: {
          action: 'watch',
          headline: 'Watch',
          summary: 'Wait.',
          reasoning: ['Wait.'],
          sourceKind: 'live_signal_model',
          sourceLabel: 'Live signal model',
          sourceTimestamp: '2026-03-10T15:30:00Z',
          severity: null,
        },
      },
      isLoading: false,
      isFetching: true,
      error: null,
      refetch: vi.fn(),
    } as never)

    render(<SymbolWorkspace symbol="vti" />)

    expect(screen.getByRole('button', { name: 'Refresh' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })
})
