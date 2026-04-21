'use client'

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { InvestingPredictionPanel } from '../InvestingPredictionPanel'

const useMarketPredictionCommitteeMock = vi.fn()
const useMarketPredictionHistoryMock = vi.fn()

vi.mock('@/lib/hooks/useMarketIntelligence', () => ({
  useMarketPredictionCommittee: (windowDays: number) =>
    useMarketPredictionCommitteeMock(windowDays),
  useMarketPredictionHistory: (
    symbol: string,
    windowDays: number,
    limit?: number,
  ) => useMarketPredictionHistoryMock(symbol, windowDays, limit),
}))

function buildCommitteeResponse(
  windowDays: number,
  overrides: Record<string, unknown> = {},
) {
  const horizonCopy = {
    1: {
      heroHeadline: 'Neutral intraday handoff with only a slight upside lean.',
      supportCopy:
        'Sentiment and regime stay balanced, but missing macro context blocks conviction.',
      bullSummary:
        'Bull case leans on a modest upside drift without broad confirmation.',
      bearSummary:
        'Confidence remains low because the macro event map is still missing.',
      rationaleSummary:
        'Balanced tape keeps the base case near flat-to-up drift.',
      expectedMovePct: 0.14,
      probUp: 0.53,
      confidenceScore: 37,
      confidenceBandLowPct: -0.15,
      confidenceBandHighPct: 0.28,
      disagreement: 0.08,
    },
    3: {
      heroHeadline: 'Slight upside drift for SPY, but edge remains weak.',
      supportCopy:
        'Calm tape with neutral sentiment and missing macro calendar risk.',
      bullSummary: 'SPY mild upside drift, low conviction',
      bearSummary:
        'Confidence remains low because macro calendar coverage is missing.',
      rationaleSummary:
        'Balanced tape keeps the base case near flat-to-up drift.',
      expectedMovePct: 0.23,
      probUp: 0.52,
      confidenceScore: 36,
      confidenceBandLowPct: -0.2,
      confidenceBandHighPct: 0.5,
      disagreement: 0.09,
    },
    7: {
      heroHeadline: 'Constructive regime, but the committee still caps upside.',
      supportCopy:
        'The tape is calm, but macro gaps and thin sector detail keep conviction modest.',
      bullSummary:
        'Bull case leans on constructive regime without a broad breakout.',
      bearSummary:
        'Confidence remains capped because macro catalysts and sector detail are incomplete.',
      rationaleSummary:
        'Constructive regime keeps the base case slightly positive.',
      expectedMovePct: 0.53,
      probUp: 0.53,
      confidenceScore: 46,
      confidenceBandLowPct: -0.4,
      confidenceBandHighPct: 1.1,
      disagreement: 0.1,
    },
    14: {
      heroHeadline: 'Range-bound to slight upside drift over two weeks.',
      supportCopy:
        'Risk stays balanced, but the missing macro calendar leaves event-gap risk live.',
      bullSummary:
        'Bull case needs the constructive regime to hold without a macro shock.',
      bearSummary:
        'Macro-event uncertainty keeps the downside gap case live over two weeks.',
      rationaleSummary:
        'Base case is flat to slight upside drift with headline risk still present.',
      expectedMovePct: 0.5,
      probUp: 0.53,
      confidenceScore: 46,
      confidenceBandLowPct: -1.1,
      confidenceBandHighPct: 1.4,
      disagreement: 0.1,
    },
  }[windowDays as 1 | 3 | 7 | 14]

  return {
    asOfTs: '2026-04-21T14:05:00Z',
    generatedAt: '2026-04-21T14:05:00Z',
    windowDays,
    baseDate: '2026-04-20',
    targetDate: windowDays === 14 ? '2026-05-08' : '2026-04-23',
    targetUniverse: ['SPY', 'XLK', 'XLF', 'XLV'],
    leadCall: {
      symbol: 'SPY',
      windowDays,
      directionLabel: 'neutral',
      probUp: horizonCopy.probUp,
      expectedMovePct: horizonCopy.expectedMovePct,
      confidenceScore: horizonCopy.confidenceScore,
      confidenceBandLowPct: horizonCopy.confidenceBandLowPct,
      confidenceBandHighPct: horizonCopy.confidenceBandHighPct,
      committeeDisagreementScore: horizonCopy.disagreement,
      rationaleSummary: horizonCopy.rationaleSummary,
      topSourceClusters: [
        { cluster: 'market_regime', weight: 0.4, freshness: 'fresh' },
        { cluster: 'options_positioning', weight: 0.4, freshness: 'fresh' },
        { cluster: 'macro_calendar', freshness: 'missing' },
      ],
    },
    calls: [
      {
        symbol: 'SPY',
        windowDays,
        directionLabel: 'neutral',
        probUp: horizonCopy.probUp,
        expectedMovePct: horizonCopy.expectedMovePct,
        confidenceScore: horizonCopy.confidenceScore,
        confidenceBandLowPct: horizonCopy.confidenceBandLowPct,
        confidenceBandHighPct: horizonCopy.confidenceBandHighPct,
        committeeDisagreementScore: horizonCopy.disagreement,
        rationaleSummary: horizonCopy.rationaleSummary,
        topSourceClusters: [{ cluster: 'market_regime', weight: 0.4 }],
      },
      {
        symbol: 'XLK',
        windowDays,
        directionLabel: 'bullish',
        probUp: 0.62,
        expectedMovePct: 0.9,
        confidenceScore: 58,
        rationaleSummary: 'Tech keeps the strongest relative upside bias.',
        topSourceClusters: [{ cluster: 'sector_rotation', weight: 0.33 }],
      },
      {
        symbol: 'XLF',
        windowDays,
        directionLabel: 'neutral',
        probUp: 0.51,
        expectedMovePct: 0.22,
        confidenceScore: 48,
        rationaleSummary:
          'Financials stay balanced while rates remain uncertain.',
        topSourceClusters: [{ cluster: 'macro', weight: 0.22 }],
      },
      {
        symbol: 'XLV',
        windowDays,
        directionLabel: 'neutral',
        probUp: 0.54,
        expectedMovePct: 0.18,
        confidenceScore: 51,
        rationaleSummary:
          'Defensives stay resilient while broad risk stays muted.',
        topSourceClusters: [{ cluster: 'defensive_flows', weight: 0.19 }],
      },
    ],
    votes: [
      {
        seatKey: 'Macro Seat',
        agentSlug: 'macro-analyst',
        modelId: 'openai/gpt-5.4',
        provider: 'openai',
        symbol: 'SPY',
        windowDays,
        directionLabel: 'neutral',
        probUp: 0.54,
        expectedMovePct: 0.2,
        confidenceScore: 50,
        rationaleSummary: 'Rates and macro uncertainty keep the room cautious.',
        sourceClusters: [{ cluster: 'macro_calendar', freshness: 'missing' }],
      },
      {
        seatKey: 'Risk Seat',
        agentSlug: 'risk-analyst',
        modelId: 'anthropic/claude-sonnet-4',
        provider: 'anthropic',
        symbol: 'SPY',
        windowDays,
        directionLabel: 'neutral',
        probUp: 0.5,
        expectedMovePct: 0.18,
        confidenceScore: 47,
        rationaleSummary:
          'Positioning is balanced, so the room is not pressing size.',
        sourceClusters: [{ cluster: 'options_positioning', weight: 0.3 }],
      },
    ],
    scorecard: {
      directionHitRate: 0.61,
      moveMaePct: 1.4,
      brierScore: 0.19,
      sampleSize: 24,
    },
    committeeSummary: {
      overallBias: horizonCopy.heroHeadline,
      marketRegimeSummary: horizonCopy.supportCopy,
      confidenceNote: horizonCopy.bearSummary,
      highestConvictionViews: [horizonCopy.bullSummary],
    },
    sourceSnapshot: {
      clusters: {
        market_regime: { freshness: 'fresh' },
        options_positioning: { freshness: 'fresh' },
        macro_calendar: { freshness: 'missing' },
      },
    },
    ...overrides,
  }
}

function buildHistoryResponse(
  windowDays: number,
  overrides: Record<string, unknown> = {},
) {
  const items =
    windowDays === 3
      ? [
          {
            symbol: 'SPY',
            windowDays,
            directionLabel: 'neutral',
            probUp: 0.56,
            expectedMovePct: 0.5,
            confidenceScore: 42,
            confidenceBandLowPct: -1.8,
            confidenceBandHighPct: 2.1,
            rationaleSummary: 'Older committee snapshot.',
            topSourceClusters: [],
          },
          {
            symbol: 'SPY',
            windowDays,
            directionLabel: 'neutral',
            probUp: 0.52,
            expectedMovePct: 0.23,
            confidenceScore: 36,
            confidenceBandLowPct: -0.2,
            confidenceBandHighPct: 0.5,
            rationaleSummary: 'Latest committee snapshot.',
            topSourceClusters: [],
          },
        ]
      : [
          {
            symbol: 'SPY',
            windowDays,
            directionLabel: 'neutral',
            probUp: 0.52,
            expectedMovePct: 0.23,
            confidenceScore: 36,
            confidenceBandLowPct: -0.2,
            confidenceBandHighPct: 0.5,
            rationaleSummary: 'Latest committee snapshot.',
            topSourceClusters: [],
          },
        ]

  return {
    symbol: 'SPY',
    windowDays,
    items,
    ...overrides,
  }
}

describe('InvestingPredictionPanel', () => {
  beforeEach(() => {
    useMarketPredictionCommitteeMock.mockReset()
    useMarketPredictionHistoryMock.mockReset()

    useMarketPredictionCommitteeMock.mockImplementation(
      (windowDays: number) => ({
        data: buildCommitteeResponse(windowDays),
        isLoading: false,
        error: null,
      }),
    )
    useMarketPredictionHistoryMock.mockImplementation(
      (symbol: string, windowDays: number, limit?: number) => ({
        data: buildHistoryResponse(windowDays),
        isLoading: false,
        error: null,
        symbol,
        limit,
      }),
    )
  })

  it('renders the committee-command-deck hero, derived scenarios, workflow rhythm, and honest gap states', () => {
    render(<InvestingPredictionPanel />)

    expect(
      screen.getByText('Slight upside drift for SPY, but edge remains weak.'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('prediction-hero')).getByText(
        'Calm tape with neutral sentiment and missing macro calendar risk.',
      ),
    ).toBeInTheDocument()
    expect(screen.getAllByText('Low disagreement').length).toBeGreaterThan(0)
    expect(screen.getByTestId('prediction-range-summary')).toHaveTextContent(
      'Range -0.20% to +0.50%',
    )

    expect(screen.getByRole('heading', { name: 'Bull' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Base' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Bear' })).toBeInTheDocument()
    expect(
      screen.getByText('SPY mild upside drift, low conviction'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Balanced tape keeps the base case near flat-to-up drift.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/No explicit bear narrative from committee\./i),
    ).toBeInTheDocument()
    expect(screen.getAllByText('Derived')).toHaveLength(3)

    expect(
      screen.getAllByText('Partial committee coverage').length,
    ).toBeGreaterThan(0)
    expect(screen.getAllByText('Missing macro context').length).toBeGreaterThan(
      0,
    )
    expect(
      screen.getByText(
        'Read the lead call, overnight handoff, and top sector tilts before the open.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Review what changed, whether the scorecard matured, and the next-session risk.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Use the scenario framing, weekly prep, and macro-event disclosure before the week starts.',
      ),
    ).toBeInTheDocument()
  })

  it('switches all four horizons and refetches the hero plus history coherently', async () => {
    const user = userEvent.setup()
    render(<InvestingPredictionPanel />)

    await user.click(screen.getByRole('button', { name: '14D' }))

    expect(useMarketPredictionCommitteeMock).toHaveBeenLastCalledWith(14)
    expect(useMarketPredictionHistoryMock).toHaveBeenLastCalledWith(
      'SPY',
      14,
      30,
    )
    expect(
      screen.getByText('Range-bound to slight upside drift over two weeks.'),
    ).toBeInTheDocument()
    expect(screen.getByTestId('prediction-range-summary')).toHaveTextContent(
      'Range -1.10% to +1.40%',
    )
  })

  it('falls back to the canonical SPY hero, filters non-canonical symbols, and deduplicates seat rows', () => {
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        leadCall: {
          symbol: 'XLK',
          windowDays: 3,
          directionLabel: 'bullish',
          probUp: 0.68,
          expectedMovePct: 0.9,
          confidenceScore: 59,
          confidenceBandLowPct: 0.2,
          confidenceBandHighPct: 1.2,
          committeeDisagreementScore: 0.18,
          rationaleSummary: 'Tech still leads the pack.',
          topSourceClusters: [],
        },
        calls: [
          {
            symbol: 'XLK',
            windowDays: 3,
            directionLabel: 'bullish',
            probUp: 0.68,
            expectedMovePct: 0.9,
            confidenceScore: 59,
            rationaleSummary: 'Tech still leads the pack.',
            topSourceClusters: [],
          },
          {
            symbol: 'spy',
            windowDays: 3,
            directionLabel: 'neutral',
            probUp: 0.52,
            expectedMovePct: 0.23,
            confidenceScore: 36,
            confidenceBandLowPct: -0.2,
            confidenceBandHighPct: 0.5,
            committeeDisagreementScore: 0.09,
            rationaleSummary:
              'Balanced tape keeps the base case near flat-to-up drift.',
            topSourceClusters: [],
          },
          {
            symbol: 'NVDA',
            windowDays: 3,
            directionLabel: 'bullish',
            probUp: 0.7,
            expectedMovePct: 2.8,
            confidenceScore: 67,
            rationaleSummary: 'Non-canonical noise should be filtered.',
            topSourceClusters: [],
          },
          {
            symbol: 'XLF',
            windowDays: 3,
            directionLabel: 'neutral',
            probUp: 0.51,
            expectedMovePct: 0.22,
            confidenceScore: 48,
            rationaleSummary: 'Financials stay balanced.',
            topSourceClusters: [],
          },
        ],
        votes: [
          {
            seatKey: 'Macro Seat',
            agentSlug: 'macro-analyst',
            modelId: 'openai/gpt-5.4',
            provider: 'openai',
            symbol: 'SPY',
            windowDays: 3,
            directionLabel: 'neutral',
            probUp: 0.54,
            expectedMovePct: 0.2,
            confidenceScore: 50,
            rationaleSummary: 'Macro stays balanced.',
            sourceClusters: [],
          },
          {
            seatKey: 'Macro Seat',
            agentSlug: 'macro-analyst-duplicate',
            modelId: 'openai/gpt-5.4',
            provider: 'openai',
            symbol: 'SPY',
            windowDays: 3,
            directionLabel: 'neutral',
            probUp: 0.55,
            expectedMovePct: 0.19,
            confidenceScore: 49,
            rationaleSummary: 'Duplicate seat should be dropped.',
            sourceClusters: [],
          },
          {
            seatKey: '',
            agentSlug: 'blank-seat',
            modelId: 'openai/gpt-5.4',
            provider: 'openai',
            symbol: 'SPY',
            windowDays: 3,
            directionLabel: 'neutral',
            probUp: 0.5,
            expectedMovePct: 0.1,
            confidenceScore: 35,
            rationaleSummary: 'Blank seat should be dropped.',
            sourceClusters: [],
          },
        ],
      }),
      isLoading: false,
      error: null,
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-hero')).toHaveTextContent('SPY')
    expect(screen.queryByText(/^NVDA$/)).not.toBeInTheDocument()
    expect(
      within(screen.getByTestId('prediction-seat-roster')).getAllByText(
        'Macro Seat',
      ),
    ).toHaveLength(1)
  })

  it('falls back to tracked-not-ranked source snapshots in deterministic freshness order', () => {
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        leadCall: {
          symbol: 'SPY',
          windowDays: 3,
          directionLabel: 'neutral',
          probUp: 0.52,
          expectedMovePct: 0.23,
          confidenceScore: 36,
          confidenceBandLowPct: -0.2,
          confidenceBandHighPct: 0.5,
          committeeDisagreementScore: 0.09,
          rationaleSummary:
            'Balanced tape keeps the base case near flat-to-up drift.',
          topSourceClusters: [],
        },
        sourceSnapshot: {
          clusters: {
            options_positioning: { freshness: 'stale' },
            macro_calendar: { freshness: 'missing' },
            market_regime: { freshness: 'fresh' },
          },
        },
      }),
      isLoading: false,
      error: null,
    })

    render(<InvestingPredictionPanel />)

    const sourceSection = screen.getByTestId('prediction-source-attribution')
    const sourceText = sourceSection.textContent ?? ''
    expect(sourceSection).toHaveTextContent('Tracked not ranked')
    expect(sourceText.indexOf('Market Regime')).toBeLessThan(
      sourceText.indexOf('Options Positioning'),
    )
    expect(sourceText.indexOf('Options Positioning')).toBeLessThan(
      sourceText.indexOf('Macro Calendar'),
    )
  })

  it('distinguishes insufficient history, scorecard pending, and history fetch errors', () => {
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        scorecard: null,
      }),
      isLoading: false,
      error: null,
    })
    useMarketPredictionHistoryMock.mockReturnValue({
      data: buildHistoryResponse(3, {
        items: [
          {
            symbol: 'SPY',
            windowDays: 3,
            directionLabel: 'neutral',
            probUp: 0.52,
            expectedMovePct: 0.23,
            confidenceScore: 36,
            confidenceBandLowPct: -0.2,
            confidenceBandHighPct: 0.5,
            rationaleSummary: 'Only one snapshot exists.',
            topSourceClusters: [],
          },
        ],
      }),
      isLoading: false,
      error: null,
    })

    const { rerender } = render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-history-state')).toHaveTextContent(
      'Insufficient history',
    )
    expect(screen.getAllByText('Pending').length).toBeGreaterThan(0)

    useMarketPredictionHistoryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('history offline'),
    })

    rerender(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-history-state')).toHaveTextContent(
      'Trend unavailable',
    )
    expect(screen.getAllByText(/history offline/i).length).toBeGreaterThan(0)
  })
})
