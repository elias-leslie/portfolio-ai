import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SymbolWorkflowPanel } from '../SymbolWorkflowPanel'

const transitionMutate = vi.fn()
const outcomeMutate = vi.fn()
const useSymbolWorkflowMock = vi.fn()
const useTransitionWorkflowMock = vi.fn()
const useRecordOutcomeMock = vi.fn()

vi.mock('@/lib/hooks/useSymbolIntelligence', () => ({
  useSymbolWorkflow: () =>
    useSymbolWorkflowMock() ?? {
      data: {
        symbol: 'VTI',
        stage: 'review_due',
        summary: 'A review is due.',
        lastTransitionAt: '2026-03-10T12:00:00Z',
        updatedBy: 'jenny',
        notes: 'Review position sizing.',
        nextReviewAt: '2026-03-12T12:00:00Z',
        availableTransitions: ['live', 'exited'],
        position: {
          shares: 10,
          costBasis: 100,
          marketValue: 1120,
          gainPct: 12,
          weightPct: 4.2,
        },
        latestOutcome: null,
        history: [],
      },
      isLoading: false,
      error: null,
    },
  useTransitionSymbolWorkflow: () =>
    useTransitionWorkflowMock() ?? {
      mutate: transitionMutate,
      isPending: false,
    },
  useRecordSymbolWorkflowOutcome: () =>
    useRecordOutcomeMock() ?? {
      mutate: outcomeMutate,
      isPending: false,
    },
}))

describe('SymbolWorkflowPanel', () => {
  it('supports both workflow transitions and outcome capture', async () => {
    useSymbolWorkflowMock.mockReset()
    useTransitionWorkflowMock.mockReset()
    useRecordOutcomeMock.mockReset()
    const user = userEvent.setup()

    render(
      <SymbolWorkflowPanel
        symbol="VTI"
        latestReview={{
          finalVerdict: 'trim',
          managementAction: 'reduce size',
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: /move to live/i }))
    await user.click(screen.getByRole('button', { name: /record trim/i }))

    expect(transitionMutate).toHaveBeenCalledWith({ stage: 'live' })
    expect(outcomeMutate).toHaveBeenCalledWith({
      action: 'trim',
      note: 'Recorded trim decision from symbol workspace.',
      jennyVerdict: 'trim',
      managementAction: 'reduce size',
    })
  })

  it('shows notes and an empty transition state when no moves are available', () => {
    useSymbolWorkflowMock.mockReturnValue({
      data: {
        symbol: 'VTI',
        stage: 'monitoring',
        summary: 'Waiting for the next catalyst.',
        lastTransitionAt: '2026-03-10T12:00:00Z',
        updatedBy: 'jenny',
        notes: 'No action until earnings.',
        nextReviewAt: null,
        availableTransitions: [],
        position: null,
        latestOutcome: null,
        history: [],
      },
      isLoading: false,
      error: null,
    })

    render(<SymbolWorkflowPanel symbol="VTI" latestReview={null} />)

    expect(screen.getByText(/no action until earnings/i)).toBeInTheDocument()
    expect(screen.getByText(/no stage transitions are available right now/i)).toBeInTheDocument()
  })

  it('marks workflow actions busy while a transition is saving', () => {
    useSymbolWorkflowMock.mockReset()
    useTransitionWorkflowMock.mockReturnValue({
      mutate: transitionMutate,
      isPending: true,
    })
    useRecordOutcomeMock.mockReturnValue({
      mutate: outcomeMutate,
      isPending: true,
    })

    render(<SymbolWorkflowPanel symbol="VTI" latestReview={null} />)

    expect(screen.getByRole('button', { name: /move to live/i })).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('button', { name: /record hold/i })).toHaveAttribute('aria-busy', 'true')
  })
})
