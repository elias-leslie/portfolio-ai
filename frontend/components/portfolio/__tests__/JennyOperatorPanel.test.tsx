import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAcknowledgeJennyNotification, useJennyDashboard, useRunJennyRoutine } from '@/lib/hooks/usePortfolio'
import { JennyOperatorPanel } from '../JennyOperatorPanel'

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useJennyDashboard: vi.fn(),
  useRunJennyRoutine: vi.fn(),
  useAcknowledgeJennyNotification: vi.fn(),
}))

describe('JennyOperatorPanel', () => {
  beforeEach(() => {
    vi.mocked(useRunJennyRoutine).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as never)
    vi.mocked(useAcknowledgeJennyNotification).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as never)
  })

  it('shows a retryable error state when the dashboard cannot load', () => {
    vi.mocked(useJennyDashboard).mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('jenny down'),
      refetch: vi.fn(),
    } as never)

    render(<JennyOperatorPanel />)

    expect(screen.getByText(/failed to load jenny operator status/i)).toBeInTheDocument()
  })

  it('shows counts and truncation hints for Jenny data', () => {
    vi.mocked(useJennyDashboard).mockReturnValue({
      data: {
        routines: [
          {
            id: 'routine-1',
            routineType: 'dailyOperator',
            status: 'completed',
            triggeredBy: 'scheduled',
            summary: 'Scanned the portfolio.',
            agentsUsed: [],
            symbolsScanned: 10,
            notificationsCreated: 6,
            startedAt: '2026-03-10T14:00:00Z',
            completedAt: '2026-03-10T14:10:00Z',
            metadata: {},
          },
        ],
        notifications: Array.from({ length: 5 }, (_, index) => ({
          id: `note-${index}`,
          routineId: 'routine-1',
          symbol: 'VTI',
          category: 'watchlist_buy_candidate',
          severity: 'info',
          status: 'open',
          title: `Alert ${index}`,
          detail: 'Detail',
          recommendation: null,
          createdAt: '2026-03-10T14:10:00Z',
          acknowledgedAt: null,
          metadata: {},
        })),
        symbolReviews: Array.from({ length: 4 }, (_, index) => ({
          symbol: `SYM${index}`,
          finalVerdict: 'buy',
          averageConfidence: 0.8,
          thesisStatus: null,
          thesisAction: null,
          managementAction: null,
          managementDetail: null,
          positionGainPct: null,
          positionWeightPct: null,
          reasons: ['Reason'],
          evaluations: [],
        })),
        tradeReviews: [],
        scorecards: Array.from({ length: 4 }, (_, index) => ({
          agentName: `Agent ${index}`,
          totalEvaluations: 10,
          completedReviews: 8,
          positiveVerdicts: 4,
          winRate: null,
          avgReturnPct: null,
          agreementRate: null,
          calibrationScore: null,
          entryQualityScore: 70,
          riskJudgmentScore: 75,
          exitTimingScore: 80,
          alertDisciplineScore: 85,
          strengths: ['Strength'],
          weaknesses: [],
          lastEvaluationAt: null,
          updatedAt: '2026-03-10T14:10:00Z',
        })),
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    } as never)

    render(<JennyOperatorPanel />)

    expect(screen.getByText(/5 alerts · 4 symbol reviews · 4 scorecards/i)).toBeInTheDocument()
    expect(screen.getByText(/latest routine completed · 10 symbols scanned · 6 alerts created · 0 critical · 0 warning · 5 other/i)).toBeInTheDocument()
    expect(screen.getByText(/showing the newest 4 of 5 alerts/i)).toBeInTheDocument()
    expect(screen.getByText(/showing the top 3 of 4 symbol reviews/i)).toBeInTheDocument()
    expect(screen.getByText(/showing the strongest 3 of 4 scorecards/i)).toBeInTheDocument()
  })
})
