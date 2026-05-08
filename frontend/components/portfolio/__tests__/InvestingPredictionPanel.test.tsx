'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { InvestingPredictionPanel } from '../InvestingPredictionPanel'

const useMarketPredictionCommitteeMock = vi.fn()
const useMarketPredictionHistoryMock = vi.fn()
const useMarketPredictionReviewMock = vi.fn()
const useRefreshMarketPredictionCommitteeMock = vi.fn()

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
    probUp: 0.453,
    expectedMovePct: -0.566,
    confidenceScore: 36,
    topSourceClusters: [
      { cluster: 'market_regime', freshness: 'fresh', asOfDate: '2026-04-29' },
    ],
    ...overrides,
  }
}

function buildCommitteeResponse(
  windowDays: number,
  overrides: JsonRecord = {},
): JsonRecord {
  return {
    asOfTs: '2026-04-29T13:15:02Z',
    generatedAt: '2026-04-29T13:15:02Z',
    windowDays,
    baseDate: '2026-04-29',
    targetDate: '2026-05-04',
    targetUniverse: ['SPY', 'XLK', 'XLF'],
    leadCall: buildCall(windowDays),
    calls: [
      buildCall(windowDays),
      buildCall(windowDays, {
        symbol: 'XLK',
        directionLabel: 'bullish',
        probUp: 0.58,
        expectedMovePct: 0.42,
      }),
    ],
    votes: [
      {
        seatKey: 'macro',
        agentSlug: 'market-pulse-analyst',
        modelId: null,
        symbol: 'SPY',
        windowDays,
        directionLabel: 'neutral',
        probUp: 0.45,
        expectedMovePct: -0.4,
        sourceClusters: [{ cluster: 'macro_calendar', freshness: 'fresh' }],
      },
    ],
    scorecard: {
      directionHitRate: 0.354,
      moveMaePct: 1.2,
      brierScore: 0.251,
      sampleSize: 48,
    },
    researchScoreboard: {
      status: 'no_edge',
      statusReason: 'Walk-forward edge is not positive after costs.',
      sampleCount: 48,
      minSampleCount: 80,
      sufficientSamples: false,
      hitRate: 0.354,
      moveMaePct: 1.2,
      brierScore: 0.251,
      baselineHitRate: 0.5,
      baselineBrierScore: 0.25,
      beatsBaseline: false,
      hitRateLcb: 0.226,
      hitRateConfident: false,
      maxMoveMaePct: 1.25,
      moveErrorOk: true,
      afterCostEdgePct: null,
      costModel: 'next_open_to_target_close_5bps_no_trades',
      modelId: null,
      modelVersion: null,
      referee: 'walk_forward_referee_v1',
      experimentLoop: 'walk_forward_grid_v1',
      walkForward: {
        status: 'fail',
        statusReason: 'Walk-forward edge is not positive after costs.',
        candidateId: 'trend_20d_t0_0',
        candidateLabel: 'trend 20d',
        driverLabels: ['SPY', 'VIX', '10Y'],
        testedCandidates: 30,
        sampleCount: 312,
        minSampleCount: 80,
        tradeCount: 220,
        hitRate: 0.51,
        hitRateLcb: 0.46,
        brierScore: 0.252,
        baselineBrierScore: 0.25,
        brierImprovementPct: -0.8,
        moveMaePct: 0.8,
        baselineMoveMaePct: 0.76,
        maxMoveMaePct: 1.25,
        afterCostEdgePct: -0.04,
        costModel: 'next_open_to_target_close_5bps',
        passed: false,
        topCandidates: [
          {
            candidateId: 'vix_rel_reversion_5d_t0_0',
            candidateLabel: 'VIX/SPY reversion 5d',
            status: 'fail',
            sampleCount: 312,
            hitRateLcb: 0.46,
            brierImprovementPct: -0.8,
            afterCostEdgePct: -0.04,
            passed: false,
          },
        ],
      },
      dataHealth: [
        {
          label: 'market_regime',
          status: 'fresh',
          detail: 'Latest closes through 2026-04-29.',
          asOfDate: '2026-04-29',
        },
      ],
    },
    committeeSummary: {
      truthState: 'live',
      scorecardStatusNote: null,
      committeeRosterMode: 'defaultRoster',
      committeeExecutionPath: 'committeeEndpoint',
      executedSeatKeys: ['macro'],
    },
    sourceSnapshot: { clusters: {} },
    freshnessSummary: {
      state: 'fresh',
      summary: 'Snapshot aligned with current market session.',
      invalidated: false,
      generatedAgeSeconds: 120,
      evaluatedAgeSeconds: 240,
      marketStatus: 'open',
      marketDate: '2026-04-29',
      refreshAfterSeconds: 900,
      checkedAt: '2026-04-29T13:17:00Z',
      reasonCodes: [],
      criticalClusters: [],
    },
    ...overrides,
  }
}

function buildReviewResponse(windowDays: number): JsonRecord {
  return {
    asOfTs: '2026-04-29T13:15:02Z',
    windowDays,
    reviewState: 'warmup',
    seatScorecards: [
      {
        seatKey: 'macro',
        priorWeight: 1 / 3,
        effectiveWeight: 1 / 3,
        sampleSize: 0,
        recommendedAction: 'hold',
      },
    ],
    reviewSummary: {
      generatedAt: '2026-04-29T13:15:02Z',
      reviewState: 'warmup',
      driftCallouts: [],
      topUpweighted: [],
      topDownweighted: [],
    },
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
        isFetching: false,
        error: null,
      }),
    )
    useMarketPredictionHistoryMock.mockImplementation(
      (symbol: string, windowDays: number, limit?: number) => ({
        data: { symbol, windowDays, items: [buildCall(windowDays)] },
        isLoading: false,
        error: null,
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
      error: null,
    })
  })

  it('renders no-edge scoreboard proof from the selected horizon', () => {
    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-research-status')).toHaveTextContent(
      'NO EDGE',
    )
    expect(screen.getByTestId('prediction-status-reason')).toHaveTextContent(
      'Walk-forward edge is not positive after costs.',
    )
    expect(screen.getByText('Fail · 312/80')).toBeInTheDocument()
    expect(screen.getByText('48/80')).toBeInTheDocument()
    expect(screen.getByText(/35.4% · n=48/i)).toBeInTheDocument()
    expect(screen.getByText('0.251')).toBeInTheDocument()
    expect(screen.getByText('trend 20d')).toBeInTheDocument()
    expect(screen.getByText('VIX/SPY reversion 5d -0.04%')).toBeInTheDocument()
    expect(screen.getAllByText('checks only').length).toBeGreaterThan(0)
  })

  it('queries only the selected horizon on initial load and switches on click', async () => {
    const user = userEvent.setup()

    render(<InvestingPredictionPanel />)

    expect(useMarketPredictionCommitteeMock).toHaveBeenCalledTimes(1)
    expect(useMarketPredictionCommitteeMock).toHaveBeenLastCalledWith(3)

    await user.click(screen.getByRole('button', { name: '14D' }))

    expect(useMarketPredictionCommitteeMock).toHaveBeenLastCalledWith(14)
    expect(useMarketPredictionHistoryMock).toHaveBeenLastCalledWith(
      'SPY',
      14,
      30,
    )
  })

  it('shows usable only when backend scoreboard says usable', () => {
    useMarketPredictionCommitteeMock.mockReturnValue({
      data: buildCommitteeResponse(3, {
        researchScoreboard: {
          status: 'usable',
          statusReason: 'Walk-forward and live checks pass after costs.',
          sampleCount: 140,
          minSampleCount: 80,
          sufficientSamples: true,
          hitRate: 0.66,
          moveMaePct: 0.7,
          brierScore: 0.18,
          baselineHitRate: 0.5,
          baselineBrierScore: 0.25,
          beatsBaseline: true,
          hitRateLcb: 0.57,
          hitRateConfident: true,
          maxMoveMaePct: 1.25,
          moveErrorOk: true,
          afterCostEdgePct: 0.18,
          costModel: 'next_open_to_target_close_5bps',
          modelId: 'scoreboard-v1',
          modelVersion: '2026-05-01',
          referee: 'walk_forward_referee_v1',
          experimentLoop: 'walk_forward_grid_v1',
          walkForward: {
            status: 'pass',
            statusReason: 'Walk-forward passed after costs.',
            candidateId: 'trend_20d_t0_0',
            candidateLabel: 'trend 20d',
            driverLabels: ['SPY', 'VIX', '10Y'],
            testedCandidates: 30,
            sampleCount: 312,
            minSampleCount: 80,
            tradeCount: 220,
            hitRate: 0.62,
            hitRateLcb: 0.56,
            brierScore: 0.22,
            baselineBrierScore: 0.25,
            brierImprovementPct: 12,
            moveMaePct: 0.7,
            baselineMoveMaePct: 0.9,
            maxMoveMaePct: 1.25,
            afterCostEdgePct: 0.18,
            costModel: 'next_open_to_target_close_5bps',
            passed: true,
            topCandidates: [
              {
                candidateId: 'trend_20d_t0_0',
                candidateLabel: 'trend 20d',
                status: 'pass',
                sampleCount: 312,
                hitRateLcb: 0.56,
                brierImprovementPct: 12,
                afterCostEdgePct: 0.18,
                passed: true,
              },
            ],
          },
          dataHealth: [],
        },
      }),
      isLoading: false,
      isFetching: false,
      error: null,
    })

    render(<InvestingPredictionPanel />)

    expect(screen.getByTestId('prediction-research-status')).toHaveTextContent(
      'USABLE',
    )
    expect(screen.getByTestId('prediction-status-reason')).toHaveTextContent(
      'Walk-forward and live checks pass after costs.',
    )
    expect(screen.getAllByText('+0.18%').length).toBeGreaterThan(0)
  })

  it('renders source attribution as-of dates', () => {
    render(<InvestingPredictionPanel />)

    expect(
      screen.getByTestId('prediction-source-attribution'),
    ).toHaveTextContent('As of 2026-04-29')
  })
})
