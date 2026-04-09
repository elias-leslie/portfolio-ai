import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HomeActionQueue } from '../HomeActionQueue'

const transitionMutate = vi.fn()
const useHomeActionQueueMock = vi.fn()

vi.mock('@/lib/hooks/useHomeActionQueue', () => ({
  useHomeActionQueue: () => useHomeActionQueueMock(),
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useAcknowledgeJennyNotification: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}))

vi.mock('@/lib/hooks/useSymbolIntelligence', () => ({
  useTransitionSymbolWorkflow: () => ({
    mutate: transitionMutate,
    isPending: false,
  }),
}))

describe('HomeActionQueue', () => {
  beforeEach(() => {
    useHomeActionQueueMock.mockReturnValue({
      data: {
        summary: '1 prioritized action ready.',
        actions: [
          {
            id: 'workflow-1',
            source: 'workflow',
            category: 'investing',
            priority: 'high',
            title: 'VTI: Initiate position',
            detail: 'Strong BUY signal (8/10) Suggested size $5,000.',
            actionLabel: 'Open decision',
            href: '/symbols/VTI?tab=decision',
            symbol: 'VTI',
            badge: 'High',
            decision: {
              action: 'INITIATE_POSITION',
              headline: 'Initiate position',
              summary: 'Strong BUY signal (8/10)',
              reasoning: ['Strong BUY signal (8/10)'],
              sourceKind: 'live_signal_model',
              sourceLabel: 'Live signal model',
              sourceTimestamp: '2026-03-10T15:30:00Z',
              severity: null,
            },
            execution: {
              kind: 'workflow_transition',
              symbol: 'VTI',
              stage: 'live',
              notificationId: null,
            },
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
  })

  it('runs the quick action workflow transition', async () => {
    const user = userEvent.setup()

    render(<HomeActionQueue />)

    expect(
      screen.getByText(
        /1 prioritized action · 1 urgent · 1 quick action-ready/i,
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/live signal model/i)).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /open decision/i }),
    ).toHaveAttribute('href', '/symbols/VTI?tab=decision')

    await user.click(screen.getByRole('button', { name: /advance workflow/i }))

    expect(transitionMutate).toHaveBeenCalledWith({
      symbol: 'VTI',
      stage: 'live',
    })
  })

  it('offers retry when the queue query fails', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    useHomeActionQueueMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('timeout'),
      refetch,
    })

    render(<HomeActionQueue />)

    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(refetch).toHaveBeenCalled()
  })

  it('shows a clear empty state when the queue is empty', () => {
    useHomeActionQueueMock.mockReturnValue({
      data: {
        generatedAt: '2026-03-11T00:00:00Z',
        summary: 'Queue clear.',
        actions: [],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<HomeActionQueue />)

    expect(
      screen.getByText(/no urgent cross-workspace actions/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Review Investing' }),
    ).toHaveAttribute('href', '/portfolio')
    expect(screen.getByRole('link', { name: 'Add Evidence' })).toHaveAttribute(
      'href',
      '/money#money-utilities',
    )
  })

  it('shows unavailable copy instead of Updated Never when generatedAt is missing', () => {
    useHomeActionQueueMock.mockReturnValue({
      data: {
        summary: 'Queue clear.',
        actions: [],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<HomeActionQueue />)

    expect(screen.getByText('Update time unavailable')).toBeInTheDocument()
    expect(screen.queryByText(/Updated Never/i)).not.toBeInTheDocument()
  })

  it('surfaces Jenny decision provenance when an alert is active', () => {
    useHomeActionQueueMock.mockReturnValue({
      data: {
        generatedAt: '2026-03-10T00:00:00Z',
        summary: '1 prioritized action ready.',
        actions: [
          {
            id: 'jenny-1',
            source: 'jenny',
            category: 'investing',
            priority: 'critical',
            title: 'NVDA: Exit this position',
            detail: 'Reduce risk now.',
            actionLabel: 'Review with Jenny',
            href: '/symbols/NVDA?tab=decision',
            symbol: 'NVDA',
            badge: 'Critical',
            decision: {
              action: 'position_exit',
              headline: 'Exit this position',
              summary: 'Reduce risk now.',
              reasoning: ['The thesis broke.', 'Reduce risk now.'],
              sourceKind: 'jenny_alert',
              sourceLabel: 'Jenny alert',
              sourceTimestamp: '2026-03-10T16:00:00Z',
              severity: 'critical',
            },
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<HomeActionQueue />)

    expect(screen.getByText(/jenny alert · critical/i)).toBeInTheDocument()
    expect(screen.getByText('Reduce risk now.')).toBeInTheDocument()
  })
})
