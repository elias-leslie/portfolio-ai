'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  fetchMarketPredictionCommittee,
  refreshMarketPredictionCommittee,
} from '@/lib/api/market-core'
import { InvestingPredictionPanel } from '../InvestingPredictionPanel'

const useMarketPredictionCommitteeMock = vi.fn()
const useMarketPredictionHistoryMock = vi.fn()
const useMarketPredictionReviewMock = vi.fn()
const useRefreshMarketPredictionCommitteeMock = vi.fn()
const originalFetch = global.fetch

vi.mock('@/lib/hooks/useMarketIntelligence', () => ({
  useMarketPredictionCommittee: (windowDays: number) =>
    useMarketPredictionCommitteeMock(windowDays),
  useMarketPredictionHistory: (
    symbol: string,
    windowDays: number,
    limit?: number,
  ) => useMarketPredictionHistoryMock(symbol, windowDays, limit),
  useMarketPredictionReview: (windowDays: number) =>
    useMarketPredictionReviewMock(windowDays),
  useRefreshMarketPredictionCommittee: () =>
    useRefreshMarketPredictionCommitteeMock(),
}))

type JsonRecord = Record<string, unknown>

function buildCall(windowDays: number, overrides: JsonRecord = {}): JsonRecord {
  return {
    symbol: 'SPY',
    windowDays,
    directionLabel: 'neutral',
    probUp: 0.52,
    expectedMovePct: 0.23,
    confidenceScore: 36,
    confidenceBandLowPct: -0.2,
    confidenceBandHighPct: 0.5,
    committeeDisagreementScore: 0.09,
    rationaleSummary:
      'Balanced tape keeps the base case near flat-to-up drift.',
    topSourceClusters: [
      { cluster: 'market_regime', weight: 0.42, freshness: 'fresh' },
      { cluster: 'options_positioning', weight: 0.33, freshness: 'fresh' },
      {
        cluster: 'macro_calendar',
        weight: null,
        freshness: 'missing',
        note: 'Awaiting scored history.',
      },
    ],
    ...overrides,
  }
}

function buildVote(
  seatKey: string,
  windowDays: number,
  overrides: JsonRecord = {},
): JsonRecord {
  return {
    seatKey,
    agentSlug: `${seatKey.toLowerCase()}-analyst`,
    modelId: 'openai/gpt-5.4',
    provider: 'openai',
    symbol: 'SPY',
    windowDays,
    directionLabel: 'neutral',
    probUp: 0.52,
    expectedMovePct: 0.23,
    confidenceScore: 48,
    rationaleSummary: `${seatKey} keeps the room balanced.`,
    sourceClusters: [{ cluster: 'market_regime', freshness: 'fresh' }],
    ...overrides,
  }
}

function buildCommitteeResponse(
  windowDays: number,
  overrides: JsonRecord = {},
): JsonRecord {
  return {
    asOfTs: '2026-04-21T14:05:00Z',
    generatedAt: '2026-04-21T14:05:00Z',
    windowDays,
    baseDate: '2026-04-20',
    targetDate: windowDays === 14 ? '2026-05-08' : '2026-04-23',
    targetUniverse: ['SPY', 'XLK', 'XLF', 'XLV'],
    leadCall: buildCall(windowDays),
    calls: [
      buildCall(windowDays),
      buildCall(windowDays, {
        symbol: 'XLK',
        directionLabel: 'bullish',
        probUp: 0.63,
        expectedMovePct: 0.91,
        confidenceScore: 59,
        rationaleSummary: 'Tech still carries the strongest upside tilt.',
        topSourceClusters: [
          { cluster: 'sector_rotation', weight: 0.35, freshness: 'fresh' },
        ],
      }),
      buildCall(windowDays, {
        symbol: 'XLF',
        directionLabel: 'neutral',
        probUp: 0.51,
        expectedMovePct: 0.18,
        confidenceScore: 45,
        rationaleSummary: 'Financials stay balanced while rates stay sticky.',
        topSourceClusters: [
          { cluster: 'macro_calendar', weight: 0.24, freshness: 'fresh' },
        ],
      }),
    ],
    votes: [
      buildVote('Macro', windowDays),
      buildVote('Cross Asset', windowDays, {
        agentSlug: 'cross-asset-analyst',
        modelId: 'xai/grok-4.20-reasoning',
      }),
      buildVote('Risk', windowDays, {
        agentSlug: 'risk-manager',
        modelId: 'claude-opus-4-7',
        provider: 'anthropic',
      }),
    ],
    scorecard: {
      directionHitRate: 0.61,
      moveMaePct: 1.4,
      brierScore: 0.19,
      sampleSize: 24,
    },
    committeeSummary: {
      heroHeadline: 'Slight upside drift for SPY, but edge remains weak.',
      marketRegimeSummary:
        'Calm tape with balanced breadth and still-sensitive macro catalysts.',
      confidenceNote:
        'The room stays constructive but does not want to press size.',
      highestConvictionViews: ['SPY mild upside drift, low conviction'],
      truthState: 'live',
      scorecardStatusNote: null,
      committeeRosterMode: 'defaultRoster',
      committeeExecutionPath: 'committeeEndpoint',
      executedSeatKeys: ['cross_asset', 'macro', 'risk'],
    },
    sourceSnapshot: {
      clusters: {
        macroCalendar: {
          freshness: 'fresh',
          reason: 'ok',
          upcomingEventCount: 3,
          nextEventDate: '2026-04-24',
        },
      },
    },
    freshnessSummary: {
      state: 'fresh',
      summary: 'Snapshot aligned with current market session.',
      invalidated: false,
      generatedAgeSeconds: 120,
      evaluatedAgeSeconds: 240,
      marketStatus: 'open',
      marketDate: '2026-04-21',
      refreshAfterSeconds: 900,
      checkedAt: '2026-04-21T14:07:00Z',
      reasonCodes: [],
      criticalClusters: [
        {
          cluster: 'market_regime',
          freshness: 'fresh',
          asOfDate: '2026-04-21',
          detail: 'Latest closes through 2026-04-21.',
        },
        {
          cluster: 'options_positioning',
          freshness: 'fresh',
          asOfDate: '2026-04-21',
          detail: 'Options positioning through 2026-04-21.',
        },
        {
          cluster: 'macro_calendar',
          freshness: 'fresh',
          asOfDate: '2026-04-21',
          detail: 'Macro calendar through 2026-04-21.',
        },
      ],
    },
    ...overrides,
  }
}

function buildHistoryResponse(
  windowDays: number,
  overrides: JsonRecord = {},
): JsonRecord {
  return {
    symbol: 'SPY',
    windowDays,
    items: [
      buildCall(windowDays, {
        expectedMovePct: 0.5,
        confidenceScore: 42,
        rationaleSummary: 'Older committee snapshot.',
      }),
      buildCall(windowDays, {
        expectedMovePct: 0.23,
        confidenceScore: 36,
        rationaleSummary: 'Latest committee snapshot.',
      }),
    ],
    ...overrides,
  }
}

function buildReviewResponse(
  windowDays: number,
  overrides: JsonRecord = {},
): JsonRecord {
  return {
    asOfTs: '2026-04-21T20:15:00Z',
    windowDays,
    reviewState: 'warmup',
    seatScorecards: [
      {
        seatKey: 'cross_asset',
        priorWeight: 1 / 3,
        effectiveWeight: 1 / 3,
        sampleSize: 0,
        avgConfidenceScore: null,
        directionHitRate: null,
        moveMaePct: null,
        brierScore: null,
        skillScore: null,
        recommendedAction: 'hold',
      },
      {
        seatKey: 'macro',
        priorWeight: 1 / 3,
        effectiveWeight: 1 / 3,
        sampleSize: 0,
        avgConfidenceScore: null,
        directionHitRate: null,
        moveMaePct: null,
        brierScore: null,
        skillScore: null,
        recommendedAction: 'hold',
      },
      {
        seatKey: 'risk',
        priorWeight: 1 / 3,
        effectiveWeight: 1 / 3,
        sampleSize: 0,
        avgConfidenceScore: null,
        directionHitRate: null,
        moveMaePct: null,
        brierScore: null,
        skillScore: null,
        recommendedAction: 'hold',
      },
    ],
    reviewSummary: {
      generatedAt: '2026-04-21T20:15:00Z',
      reviewState: 'warmup',
      driftCallouts: [],
      topUpweighted: [],
      topDownweighted: [],
    },
    ...overrides,
  }
}

describe('InvestingPredictionPanel', () => {
  beforeEach(() => {
    useMarketPredictionCommitteeMock.mockReset()
    useMarketPredictionHistoryMock.mockReset()
    useMarketPredictionReviewMock.mockReset()
    useRefreshMarketPredictionCommitteeMock.mockReset()

    useMarketPredictionCommitteeMock.mockImplementation(
      (windowDays: number) => ({
        data: buildCommitteeResponse(windowDays),
        isLoading: false,
        error: null,
      }),
    )
    useMarketPredictionHistoryMock.mockImplementation(
      (symbol: string, windowDays: number, limit?: number) => ({
        data: buildHistoryResponse(windowDays, { symbol }),
        isLoading: false,
        error: null,
        symbol,
        limit,
      }),
    )
    useMarketPredictionReviewMock.mockImplementation((windowDays: number) => ({
      data: buildReviewResponse(windowDays),
      isLoading: false,
      error: null,
    }))
    useRefreshMarketPredictionCommitteeMock.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('renders live truth, roster, and macro calendar detail without inventing attribution from sourceSnapshot', () => {
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        leadCall: buildCall(3, {
          topSourceClusters: [
            { cluster: 'options_positioning', weight: 0.5, freshness: 'fresh' },
          ],
        }),
        committeeSummary: {
          heroHeadline: 'Committee stays balanced while macro risk lingers.',
          marketRegimeSummary:
            'Live regime stays calm, but event density is still thin.',
          truthState: 'live',
          scorecardStatusNote: null,
          committeeRosterMode: 'customRoster',
          committeeExecutionPath: 'committeeEndpoint',
          executedSeatKeys: ['macro', 'risk'],
        },
        sourceSnapshot: {
          clusters: {
            macroCalendar: {
              freshness: 'missing',
              reason: 'noFutureRows',
              upcomingEventCount: 0,
              nextEventDate: null,
            },
          },
        },
        freshnessSummary: {
          state: 'stale',
          summary: 'Snapshot is running with missing evidence coverage.',
          invalidated: false,
          generatedAgeSeconds: 5400,
          evaluatedAgeSeconds: null,
          marketStatus: 'open',
          marketDate: '2026-04-21',
          refreshAfterSeconds: 300,
          checkedAt: '2026-04-21T15:35:00Z',
          reasonCodes: ['macro_calendar_missing'],
          criticalClusters: [
            {
              cluster: 'market_regime',
              freshness: 'fresh',
              asOfDate: '2026-04-21',
              detail: 'Latest closes through 2026-04-21.',
            },
            {
              cluster: 'options_positioning',
              freshness: 'fresh',
              asOfDate: '2026-04-21',
              detail: 'Options positioning through 2026-04-21.',
            },
            {
              cluster: 'macro_calendar',
              freshness: 'missing',
              asOfDate: null,
              detail: 'No future macro rows tracked.',
            },
          ],
        },
      }),
      isLoading: false,
      error: null,
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-truth-state')).toHaveTextContent(
      'Live',
    )
    expect(screen.getByTestId('prediction-seat-roster')).toHaveTextContent(
      'Custom Roster',
    )
    expect(screen.getByTestId('prediction-seat-roster')).toHaveTextContent(
      'Seats used: Macro, Risk',
    )
    expect(screen.getByTestId('prediction-hero')).toHaveTextContent(
      '3 trading days: Apr 20, 2026 close to Apr 23, 2026 close',
    )
    expect(screen.getByTestId('prediction-hero')).toHaveTextContent(
      /Forecast 3 trading days: Apr 20, 2026 close to Apr 23, 2026 close · made Apr 21/i,
    )
    expect(
      screen.getByText('Committee stays balanced while macro risk lingers.'),
    ).toBeInTheDocument()
    const sourceSection = screen.getByTestId('prediction-source-attribution')
    expect(sourceSection).toHaveTextContent('Options Positioning')
    expect(sourceSection).toHaveTextContent('Rank 50%')
    expect(sourceSection).toHaveTextContent('Macro Calendar')
    expect(sourceSection).toHaveTextContent('Awaiting scored history')
    expect(screen.getByTestId('prediction-freshness-state')).toHaveTextContent(
      'Old',
    )
    expect(screen.getByTestId('prediction-freshness-rail')).toHaveTextContent(
      'No future macro rows tracked.',
    )
  })

  it('surfaces invalidated snapshots above fold with last-made timing and refresh requirement', async () => {
    const user = userEvent.setup()
    const refreshMutate = vi.fn()
    useRefreshMarketPredictionCommitteeMock.mockReturnValue({
      mutate: refreshMutate,
      isPending: false,
    })
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        generatedAt: '2026-04-20T20:15:00Z',
        asOfTs: '2026-04-20T20:15:00Z',
        lastEvaluatedAt: null,
        committeeSummary: {
          truthState: 'waitingAfterClose',
          scorecardStatusNote:
            'Target date passed, but the post-close evaluation has not published yet.',
          committeeRosterMode: 'defaultRoster',
          committeeExecutionPath: 'committeeEndpoint',
          executedSeatKeys: ['cross_asset', 'macro', 'risk'],
        },
        freshnessSummary: {
          state: 'invalid',
          summary: 'Target date passed. Refresh after evaluation publishes.',
          invalidated: true,
          generatedAgeSeconds: 54_000,
          evaluatedAgeSeconds: null,
          marketStatus: 'open',
          marketDate: '2026-04-21',
          refreshAfterSeconds: 60,
          checkedAt: '2026-04-21T11:15:00Z',
          reasonCodes: ['target_reached_pending_evaluation'],
          criticalClusters: [
            {
              cluster: 'market_regime',
              freshness: 'stale',
              asOfDate: '2026-04-20',
              detail: 'Latest closes through 2026-04-20.',
            },
          ],
        },
      }),
      isLoading: false,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-freshness-state')).toHaveTextContent(
      'Needs refresh',
    )
    expect(
      screen.getByTestId('prediction-freshness-summary'),
    ).toHaveTextContent(
      'Target date passed. Refresh after evaluation publishes.',
    )
    expect(
      screen.getByTestId('prediction-last-generated-at'),
    ).toHaveTextContent('Apr')
    expect(screen.getByTestId('prediction-freshness-rail')).toHaveTextContent(
      'Refresh needed',
    )
    await user.click(screen.getByRole('button', { name: /refresh now/i }))
    expect(refreshMutate).toHaveBeenCalledWith(3)
  })

  it('shows refresh failures next to freshness evidence', () => {
    useRefreshMarketPredictionCommitteeMock.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      error: new Error('Committee refresh failed'),
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByRole('status')).toHaveTextContent(
      'Refresh failed: Committee refresh failed',
    )
  })

  it('renders learning track record with agent models and seat trends', () => {
    useMarketPredictionReviewMock.mockReturnValue({
      data: buildReviewResponse(3, {
        asOfTs: '2026-04-21T20:20:00Z',
        reviewState: 'live',
        seatScorecards: [
          {
            seatKey: 'cross_asset',
            priorWeight: 1 / 3,
            effectiveWeight: 0.29,
            sampleSize: 9,
            avgConfidenceScore: 44,
            directionHitRate: 0.57,
            moveMaePct: 0.8,
            brierScore: 0.19,
            skillScore: 0.62,
            recommendedAction: 'hold',
          },
          {
            seatKey: 'macro',
            priorWeight: 1 / 3,
            effectiveWeight: 0.39,
            sampleSize: 12,
            avgConfidenceScore: 62,
            directionHitRate: 0.66,
            moveMaePct: 0.61,
            brierScore: 0.16,
            skillScore: 0.74,
            recommendedAction: 'upweight',
          },
          {
            seatKey: 'risk',
            priorWeight: 1 / 3,
            effectiveWeight: 0.32,
            sampleSize: 7,
            avgConfidenceScore: 51,
            directionHitRate: 0.51,
            moveMaePct: 0.92,
            brierScore: 0.22,
            skillScore: 0.58,
            recommendedAction: 'downweight',
          },
        ],
        reviewSummary: {
          generatedAt: '2026-04-21T20:20:00Z',
          reviewState: 'live',
          driftCallouts: ['macro upweighted from 0.3333 to 0.3900'],
          topUpweighted: [
            {
              kind: 'seat',
              key: 'macro',
              priorWeight: 1 / 3,
              effectiveWeight: 0.39,
            },
          ],
          topDownweighted: [],
        },
        reviewHistory: [
          {
            generatedAt: '2026-04-20T20:20:00Z',
            asOfTs: '2026-04-20T20:20:00Z',
            reviewState: 'live',
            seatScorecards: [
              {
                seatKey: 'cross_asset',
                priorWeight: 1 / 3,
                effectiveWeight: 0.31,
                sampleSize: 8,
                avgConfidenceScore: 41,
                directionHitRate: 0.55,
                moveMaePct: 0.9,
                brierScore: 0.2,
                skillScore: 0.6,
                recommendedAction: 'hold',
              },
              {
                seatKey: 'macro',
                priorWeight: 1 / 3,
                effectiveWeight: 0.35,
                sampleSize: 10,
                avgConfidenceScore: 58,
                directionHitRate: 0.61,
                moveMaePct: 0.7,
                brierScore: 0.18,
                skillScore: 0.69,
                recommendedAction: 'hold',
              },
              {
                seatKey: 'risk',
                priorWeight: 1 / 3,
                effectiveWeight: 0.34,
                sampleSize: 6,
                avgConfidenceScore: 52,
                directionHitRate: 0.49,
                moveMaePct: 1.0,
                brierScore: 0.24,
                skillScore: 0.55,
                recommendedAction: 'hold',
              },
            ],
          },
          {
            generatedAt: '2026-04-21T20:20:00Z',
            asOfTs: '2026-04-21T20:20:00Z',
            reviewState: 'live',
            seatScorecards: [
              {
                seatKey: 'cross_asset',
                priorWeight: 1 / 3,
                effectiveWeight: 0.29,
                sampleSize: 9,
                avgConfidenceScore: 44,
                directionHitRate: 0.57,
                moveMaePct: 0.8,
                brierScore: 0.19,
                skillScore: 0.62,
                recommendedAction: 'hold',
              },
              {
                seatKey: 'macro',
                priorWeight: 1 / 3,
                effectiveWeight: 0.39,
                sampleSize: 12,
                avgConfidenceScore: 62,
                directionHitRate: 0.66,
                moveMaePct: 0.61,
                brierScore: 0.16,
                skillScore: 0.74,
                recommendedAction: 'upweight',
              },
              {
                seatKey: 'risk',
                priorWeight: 1 / 3,
                effectiveWeight: 0.32,
                sampleSize: 7,
                avgConfidenceScore: 51,
                directionHitRate: 0.51,
                moveMaePct: 0.92,
                brierScore: 0.22,
                skillScore: 0.58,
                recommendedAction: 'downweight',
              },
            ],
          },
        ],
      }),
      isLoading: false,
      error: null,
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-review-panel')).toHaveTextContent(
      'Learning track record',
    )
    expect(screen.getByTestId('prediction-seat-roster')).toHaveTextContent(
      'Model: openai/gpt-5.4',
    )
    expect(screen.getByTestId('prediction-seat-roster')).toHaveTextContent(
      'Agent: macro-analyst',
    )
    expect(
      screen.getByTestId('prediction-review-seat-weights'),
    ).toHaveTextContent('Macro')
    expect(
      screen.getByTestId('prediction-review-seat-weights'),
    ).toHaveTextContent('39%')
    expect(
      screen.getByTestId('prediction-review-seat-weights'),
    ).toHaveTextContent('Trust rising')
    expect(
      screen.getByTestId('prediction-review-seat-weights'),
    ).toHaveTextContent('62/100')
    expect(
      screen.getByTestId('prediction-review-seat-weights'),
    ).toHaveTextContent('Improving')
  })

  it('switches horizons and keeps the selected-truth badge wired to each window payload', async () => {
    const user = userEvent.setup()
    useMarketPredictionCommitteeMock.mockImplementation(
      (windowDays: number) => ({
        data: buildCommitteeResponse(windowDays, {
          committeeSummary: {
            truthState: windowDays === 14 ? 'pendingTarget' : 'live',
            scorecardStatusNote:
              windowDays === 14
                ? 'Two-week cohort has not reached target yet.'
                : null,
            committeeRosterMode: 'defaultRoster',
            committeeExecutionPath: 'committeeEndpoint',
            executedSeatKeys: ['cross_asset', 'macro', 'risk'],
          },
        }),
        isLoading: false,
        error: null,
      }),
    )

    render(<InvestingPredictionPanel />)

    await user.click(
      screen.getByRole('button', { name: '14 trading days forecast' }),
    )

    expect(useMarketPredictionCommitteeMock).toHaveBeenLastCalledWith(14)
    expect(useMarketPredictionHistoryMock).toHaveBeenLastCalledWith(
      'SPY',
      14,
      30,
    )
    expect(screen.getByTestId('prediction-truth-state')).toHaveTextContent(
      'Awaiting target close',
    )
    expect(screen.getByTestId('prediction-truth-note')).toHaveTextContent(
      'Two-week forecast has not reached target yet.',
    )
  })

  it('renders pendingTarget and waitingAfterClose truth states from backend notes', () => {
    let selectedSnapshot = buildCommitteeResponse(3, {
      committeeSummary: {
        truthState: 'pendingTarget',
        scorecardStatusNote:
          'Current 3D cohort targets Apr 23, 2026. Scorecard populates after the first post-close evaluation.',
        committeeRosterMode: 'defaultRoster',
        committeeExecutionPath: 'committeeEndpoint',
        executedSeatKeys: ['cross_asset', 'macro', 'risk'],
      },
      scorecard: null,
    })

    useMarketPredictionCommitteeMock.mockImplementation(
      (windowDays: number) => ({
        data:
          windowDays === 3
            ? selectedSnapshot
            : buildCommitteeResponse(windowDays),
        isLoading: false,
        error: null,
      }),
    )

    const { rerender } = render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-truth-state')).toHaveTextContent(
      'Awaiting target close',
    )
    expect(screen.getByTestId('prediction-truth-note')).toHaveTextContent(
      'Current 3 trading days forecast targets Apr 23, 2026.',
    )

    selectedSnapshot = buildCommitteeResponse(3, {
      committeeSummary: {
        truthState: 'waitingAfterClose',
        scorecardStatusNote:
          'Target date passed, but the post-close evaluation has not published yet.',
        committeeRosterMode: 'defaultRoster',
        committeeExecutionPath: 'committeeEndpoint',
        executedSeatKeys: ['cross_asset', 'macro', 'risk'],
      },
      scorecard: null,
    })

    rerender(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-truth-state')).toHaveTextContent(
      'Waiting for score',
    )
    expect(screen.getByTestId('prediction-truth-note')).toHaveTextContent(
      'Target date passed. Waiting for the scored result.',
    )
  })

  it('renders sparseHistory from backend truth and keeps the trend panel local to sparse history', () => {
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        committeeSummary: {
          truthState: 'sparseHistory',
          scorecardStatusNote:
            'Live scorecard exists, but the selected lead history still needs more usable committee snapshots.',
          committeeRosterMode: 'defaultRoster',
          committeeExecutionPath: 'committeeEndpoint',
          executedSeatKeys: ['cross_asset', 'macro', 'risk'],
        },
      }),
      isLoading: false,
      error: null,
    })
    useMarketPredictionHistoryMock.mockReturnValue({
      data: buildHistoryResponse(3, {
        items: [buildCall(3, { expectedMovePct: 0.23 })],
      }),
      isLoading: false,
      error: null,
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-truth-state')).toHaveTextContent(
      'Limited history',
    )
    expect(screen.getByTestId('prediction-history-state')).toHaveTextContent(
      'Insufficient history',
    )
    expect(screen.getByTestId('prediction-truth-note')).toHaveTextContent(
      'Need more scored forecasts for a reliable trend.',
    )
  })

  it('renders fetchError from backend truth without promoting it to legacy sparse', () => {
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        leadCall: buildCall(3, { topSourceClusters: [] }),
        calls: [buildCall(3, { topSourceClusters: [] })],
        votes: [],
        scorecard: null,
        committeeSummary: {
          truthState: 'fetchError',
          scorecardStatusNote:
            'Prediction snapshot degraded on fetch. Showing the latest safe fallback contract until a healthy refresh returns.',
          committeeRosterMode: null,
          committeeExecutionPath: 'fallbackCompletion',
          executedSeatKeys: [],
        },
      }),
      isLoading: false,
      error: null,
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-truth-state')).toHaveTextContent(
      'Refresh failed',
    )
    expect(screen.getByTestId('prediction-truth-note')).toHaveTextContent(
      'Latest refresh failed. Showing fallback data.',
    )
    const sourceSection = screen.getByTestId('prediction-source-attribution')
    expect(sourceSection).toHaveTextContent('Market Regime')
    expect(sourceSection).toHaveTextContent('Options Positioning')
    expect(sourceSection).toHaveTextContent('Macro Calendar')
    expect(sourceSection).not.toHaveTextContent(
      'Source attribution is unavailable',
    )
  })

  it('keeps a history-only trend failure local when backend truthState remains live even with malformed sibling provenance', () => {
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        committeeSummary: {
          truthState: 'live',
          scorecardStatusNote: null,
          committeeRosterMode: 'defaultRoster',
          committeeExecutionPath: [],
          executedSeatKeys: ['cross_asset', 'macro', 'risk'],
        },
        sourceSnapshot: {
          clusters: {
            macroCalendar: 'bad sibling provenance',
          },
        },
      }),
      isLoading: false,
      error: null,
    })
    useMarketPredictionHistoryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('history offline'),
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-truth-state')).toHaveTextContent(
      'Live',
    )
    expect(
      screen.queryByTestId('prediction-truth-note'),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('prediction-history-state')).toHaveTextContent(
      'Trend unavailable',
    )
    expect(screen.getAllByText(/history offline/i).length).toBeGreaterThan(0)
    expect(screen.getByTestId('prediction-truth-state')).not.toHaveTextContent(
      'Refresh failed',
    )
  })

  it('falls back from an unattributed top-level lead to SPY, then to the first normalized call with surviving attribution', () => {
    let selectedSnapshot = buildCommitteeResponse(3, {
      leadCall: buildCall(3, {
        symbol: 'XLK',
        topSourceClusters: [],
      }),
      calls: [
        buildCall(3, {
          symbol: ' spy ',
          topSourceClusters: [
            { cluster: 'market_regime', weight: 0.4, freshness: 'fresh' },
          ],
        }),
        buildCall(3, {
          symbol: 'XLF',
          topSourceClusters: [
            { cluster: 'macro_calendar', weight: 0.2, freshness: 'fresh' },
          ],
        }),
      ],
    })

    useMarketPredictionCommitteeMock.mockImplementation(
      (windowDays: number) => ({
        data:
          windowDays === 3
            ? selectedSnapshot
            : buildCommitteeResponse(windowDays),
        isLoading: false,
        error: null,
      }),
    )

    const { rerender } = render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-hero')).toHaveTextContent('SPY')
    expect(useMarketPredictionHistoryMock).toHaveBeenLastCalledWith(
      'SPY',
      3,
      30,
    )

    selectedSnapshot = buildCommitteeResponse(3, {
      leadCall: buildCall(3, {
        symbol: 'XLK',
        topSourceClusters: [],
      }),
      calls: [
        buildCall(3, {
          symbol: 'SPY',
          topSourceClusters: [],
        }),
        buildCall(3, {
          symbol: 'XLF',
          topSourceClusters: [
            { cluster: 'macro_calendar', weight: 0.2, freshness: 'fresh' },
          ],
        }),
        buildCall(3, {
          symbol: 'NVDA',
          topSourceClusters: [
            { cluster: 'sentiment', weight: 0.1, freshness: 'fresh' },
          ],
        }),
      ],
    })

    rerender(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-hero')).toHaveTextContent('XLF')
    expect(useMarketPredictionHistoryMock).toHaveBeenLastCalledWith(
      'XLF',
      3,
      30,
    )
  })

  it('stays in legacySparse precedence when truthState is invalid and no surviving attribution exists, even if history fetch fails', () => {
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        leadCall: buildCall(3, { topSourceClusters: [] }),
        calls: [
          buildCall(3, { topSourceClusters: [] }),
          buildCall(3, {
            symbol: 'XLF',
            topSourceClusters: [{ cluster: '' }, 'bad row'] as unknown as [],
          }),
        ],
        committeeSummary: 'malformed legacy payload',
      }),
      isLoading: false,
      error: null,
    })
    useMarketPredictionHistoryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('history offline'),
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-truth-state')).toHaveTextContent(
      'Older data',
    )
    expect(screen.getByTestId('prediction-truth-note')).toHaveTextContent(
      'Older data lacks source detail.',
    )
    expect(
      screen.getByTestId('prediction-source-attribution'),
    ).toHaveTextContent('Awaiting scored history')
    expect(screen.getByTestId('prediction-history-state')).toHaveTextContent(
      'Trend unavailable',
    )
    expect(screen.getByTestId('prediction-truth-state')).not.toHaveTextContent(
      'Refresh failed',
    )
  })

  it('handles snake_case backend additive fields end-to-end after client key camel-casing', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        as_of_ts: '2026-04-21T14:05:00Z',
        generated_at: '2026-04-21T14:05:00Z',
        window_days: 3,
        base_date: '2026-04-20',
        target_date: '2026-04-23',
        target_universe: ['SPY'],
        lead_call: {
          symbol: 'SPY',
          window_days: 3,
          direction_label: 'neutral',
          prob_up: 0.5,
          expected_move_pct: 0.0,
          top_source_clusters: [
            { cluster: 'macro_calendar', freshness: 'missing', weight: null },
          ],
        },
        calls: [
          {
            symbol: 'SPY',
            window_days: 3,
            direction_label: 'neutral',
            prob_up: 0.5,
            expected_move_pct: 0.0,
            top_source_clusters: [
              { cluster: 'macro_calendar', freshness: 'missing', weight: null },
            ],
          },
        ],
        votes: [],
        scorecard: null,
        committee_summary: {
          truth_state: 'pending_target',
          scorecard_status_note: 'backend note',
          committee_roster_mode: 'default_roster',
          committee_execution_path: 'committee_endpoint',
          executed_seat_keys: ['macro', 'risk'],
        },
        source_snapshot: {
          clusters: {
            macro_calendar: {
              freshness: 'missing',
              reason: 'no_future_rows',
              upcoming_event_count: 0,
              next_event_date: null,
            },
          },
        },
        freshness_summary: {
          state: 'stale',
          summary: 'Snapshot is running with missing evidence coverage.',
          invalidated: false,
          generated_age_seconds: 5400,
          evaluated_age_seconds: null,
          market_status: 'open',
          market_date: '2026-04-21',
          refresh_after_seconds: 300,
          checked_at: '2026-04-21T15:35:00Z',
          reason_codes: ['macro_calendar_missing'],
          critical_clusters: [
            {
              cluster: 'macro_calendar',
              freshness: 'missing',
              as_of_date: null,
              detail: 'No future macro rows tracked.',
            },
          ],
        },
      }),
    })

    const response = await fetchMarketPredictionCommittee(3)

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/market/prediction/committee?window_days=3',
      expect.objectContaining({ cache: 'no-store' }),
    )
    expect(response.committeeSummary).toEqual(
      expect.objectContaining({
        truthState: 'pending_target',
        scorecardStatusNote: 'backend note',
        committeeRosterMode: 'default_roster',
        committeeExecutionPath: 'committee_endpoint',
        executedSeatKeys: ['macro', 'risk'],
      }),
    )
    expect(response.sourceSnapshot.clusters?.macroCalendar).toEqual(
      expect.objectContaining({
        freshness: 'missing',
        reason: 'no_future_rows',
        upcomingEventCount: 0,
        nextEventDate: null,
      }),
    )

    useMarketPredictionCommitteeMock.mockReturnValue({
      data: response,
      isLoading: false,
      error: null,
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-truth-state')).toHaveTextContent(
      'Awaiting target close',
    )
    expect(screen.getByTestId('prediction-truth-note')).toHaveTextContent(
      'backend note',
    )
    expect(screen.getByTestId('prediction-seat-roster')).toHaveTextContent(
      'Default Roster',
    )
    const sourceSection = screen.getByTestId('prediction-source-attribution')
    expect(sourceSection).toHaveTextContent('Macro Calendar')
    expect(sourceSection).toHaveTextContent('Awaiting scored history')
    expect(sourceSection).toHaveTextContent('No future macro rows tracked.')
    expect(screen.getByTestId('prediction-freshness-state')).toHaveTextContent(
      'Old',
    )

    const refreshed = await refreshMarketPredictionCommittee(3)

    expect(global.fetch).toHaveBeenLastCalledWith(
      '/api/market/prediction/committee/refresh?window_days=3',
      expect.objectContaining({
        cache: 'no-store',
        method: 'POST',
      }),
    )
    expect(refreshed.freshnessSummary?.reasonCodes).toEqual([
      'macro_calendar_missing',
    ])
  })
})
