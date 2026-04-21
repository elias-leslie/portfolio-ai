'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { InvestingPredictionPanel } from '../InvestingPredictionPanel'

const useMarketPredictionCommitteeMock = vi.fn()

vi.mock('@/lib/hooks/useMarketIntelligence', () => ({
  useMarketPredictionCommittee: (windowDays: number) =>
    useMarketPredictionCommitteeMock(windowDays),
}))

describe('InvestingPredictionPanel', () => {
  beforeEach(() => {
    useMarketPredictionCommitteeMock.mockImplementation((windowDays: number) => ({
      data: {
        windowDays,
        targetUniverse: ['SPY', 'XLK', 'XLF'],
        leadCall: {
          symbol: 'SPY',
          windowDays,
          directionLabel: windowDays === 14 ? 'neutral' : 'bullish',
          probUp: windowDays === 14 ? 0.52 : 0.64,
          expectedMovePct: windowDays === 14 ? 0.3 : 1.8,
          confidenceScore: windowDays === 14 ? 58 : 78,
          rationaleSummary:
            windowDays === 14
              ? 'Longer horizon still has cross-currents.'
              : 'Breadth and options positioning improved.',
          topSourceClusters: [
            { cluster: 'market_regime', weight: 0.35 },
            { cluster: 'options_positioning', weight: 0.25 },
          ],
        },
        calls: [
          {
            symbol: 'SPY',
            windowDays,
            directionLabel: 'bullish',
            probUp: 0.64,
            expectedMovePct: 1.8,
            confidenceScore: 78,
            rationaleSummary: 'Lead market call.',
            topSourceClusters: [{ cluster: 'market_regime', weight: 0.35 }],
          },
          {
            symbol: 'XLK',
            windowDays,
            directionLabel: 'bullish',
            probUp: 0.68,
            expectedMovePct: 2.4,
            confidenceScore: 81,
            rationaleSummary: 'Tech leadership stays intact.',
            topSourceClusters: [{ cluster: 'sector_rotation', weight: 0.4 }],
          },
          {
            symbol: 'XLF',
            windowDays,
            directionLabel: 'neutral',
            probUp: 0.51,
            expectedMovePct: 0.2,
            confidenceScore: 56,
            rationaleSummary: 'Banks remain range-bound.',
            topSourceClusters: [{ cluster: 'macro', weight: 0.22 }],
          },
        ],
        votes: [
          {
            seatKey: 'macro',
            agentSlug: 'market-pulse-analyst',
            modelId: 'openai/gpt-5.4',
            provider: 'openai',
            symbol: 'SPY',
            windowDays,
            directionLabel: 'bullish',
            probUp: 0.66,
            expectedMovePct: 2.0,
            confidenceScore: 82,
            rationaleSummary: 'Rates and breadth are supportive.',
            sourceClusters: [{ cluster: 'macro', weight: 0.4 }],
          },
        ],
        scorecard: {
          directionHitRate: 0.61,
          moveMaePct: 1.4,
          brierScore: 0.19,
          sampleSize: 48,
        },
        committeeSummary: {
          headline: 'Constructive risk appetite with moderate disagreement.',
          disagreementLabel: 'moderate',
        },
        sourceSnapshot: {
          clusters: {
            market_regime: { freshness: 'fresh' },
            options_positioning: { freshness: 'fresh' },
          },
        },
      },
      isLoading: false,
      error: null,
    }))
  })

  it('renders the committee hero, sector board, and scorecard for the selected window', async () => {
    const user = userEvent.setup()
    render(<InvestingPredictionPanel />)

    expect(screen.getByText(/market prediction committee/i)).toBeInTheDocument()
    expect(screen.getByText(/constructive risk appetite/i)).toBeInTheDocument()
    expect(screen.getAllByText(/^SPY$/i)[0]).toBeInTheDocument()
    expect(screen.getByText(/Breadth and options positioning improved/i)).toBeInTheDocument()
    expect(screen.getByText(/^XLK$/i)).toBeInTheDocument()
    expect(screen.getByText(/direction hit rate/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '14D' }))

    expect(useMarketPredictionCommitteeMock).toHaveBeenLastCalledWith(14)
    expect(screen.getByText(/longer horizon still has cross-currents/i)).toBeInTheDocument()
  })
})
