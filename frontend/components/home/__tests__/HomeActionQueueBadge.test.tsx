import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HomeActionQueueBadge } from '../HomeActionQueueBadge'

const mutate = vi.fn()
let pending = false
let failed = false
const action = {
  id: 'question-action',
  title: 'Do you shop here regularly?',
  detail: 'Records shopping frequency.',
  category: 'household',
  priority: 'medium',
  href: '/money?tab=intake',
  actionLabel: 'Answer question',
  question: { id: 'question-1', format: 'boolean', options: [] as string[] },
}

vi.mock('@/components/providers/HomeActionQueueProvider', () => ({
  useHomeActionQueueState: () => ({
    visibleActions: [action],
    isLoading: false,
    error: null,
  }),
}))
vi.mock('@/lib/hooks/useHousehold', () => ({
  useAnswerHouseholdQuestion: () => ({
    mutate,
    isPending: pending,
    isError: failed,
  }),
}))

describe('top-bar Actions answers', () => {
  beforeEach(() => {
    mutate.mockReset()
    pending = false
    failed = false
    action.question = { id: 'question-1', format: 'boolean', options: [] }
  })

  it.each([
    'Yes',
    'No',
  ])('keeps answers hidden until opened and saves %s without navigation', (label) => {
    render(<HomeActionQueueBadge />)
    expect(screen.queryByText(action.title)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Action Queue/ }))
    const popover = screen.getByRole('dialog', { name: 'Action Queue' })
    expect(
      within(popover).queryByRole('link', { name: 'Answer question' }),
    ).not.toBeInTheDocument()
    fireEvent.click(within(popover).getByRole('button', { name: label }))
    expect(mutate).toHaveBeenCalledExactlyOnceWith({
      questionId: 'question-1',
      answerText: label.toLowerCase(),
    })
    expect(popover).toBeVisible()
  })

  it('offers supplied choices directly', () => {
    action.question = {
      id: 'choice-1',
      format: 'single_select',
      options: ['Monthly', 'Annually'],
    }
    render(<HomeActionQueueBadge />)
    fireEvent.click(screen.getByRole('button', { name: /Action Queue/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Annually' }))
    expect(mutate).toHaveBeenCalledWith({
      questionId: 'choice-1',
      answerText: 'Annually',
    })
  })

  it('preserves a failed answer for retry and blocks duplicate submissions while saving', () => {
    failed = true
    pending = true
    render(<HomeActionQueueBadge />)
    fireEvent.click(screen.getByRole('button', { name: /Action Queue/ }))
    expect(screen.getByRole('button', { name: 'Yes' })).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent('Answer wasn’t saved')
    expect(screen.getByText(action.title)).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Yes' }))
    expect(mutate).not.toHaveBeenCalled()
  })
})
