import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { HomeActionQueue } from '../HomeActionQueue'

const transitionMutate = vi.fn()

vi.mock('@/lib/hooks/useHomeActionQueue', () => ({
  useHomeActionQueue: () => ({
    data: {
      summary: '1 prioritized action ready.',
      actions: [
        {
          id: 'workflow-1',
          source: 'workflow',
          category: 'investing',
          priority: 'high',
          title: 'Review VTI',
          detail: 'Review the workflow state.',
          actionLabel: 'Open symbol',
          href: '/symbols/VTI',
          symbol: 'VTI',
          badge: 'High',
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
    error: null,
  }),
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
  it('runs the quick action workflow transition', async () => {
    const user = userEvent.setup()

    render(<HomeActionQueue />)

    await user.click(screen.getByRole('button', { name: /quick action/i }))

    expect(transitionMutate).toHaveBeenCalledWith({
      symbol: 'VTI',
      stage: 'live',
    })
  })
})
