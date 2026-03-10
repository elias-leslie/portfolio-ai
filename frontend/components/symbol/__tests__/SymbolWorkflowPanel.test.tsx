import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SymbolWorkflowPanel } from '../SymbolWorkflowPanel'

const transitionMutate = vi.fn()
const outcomeMutate = vi.fn()

vi.mock('@/lib/hooks/useSymbolIntelligence', () => ({
  useSymbolWorkflow: () => ({
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
  }),
  useTransitionSymbolWorkflow: () => ({
    mutate: transitionMutate,
    isPending: false,
  }),
  useRecordSymbolWorkflowOutcome: () => ({
    mutate: outcomeMutate,
    isPending: false,
  }),
}))

describe('SymbolWorkflowPanel', () => {
  it('supports both workflow transitions and outcome capture', async () => {
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
})
