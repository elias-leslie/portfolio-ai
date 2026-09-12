import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { HomeAccountOptions } from '../HomeAccountOptions'

const mutate = vi.fn()
const card = {
  id: 'card-1',
  householdAccountId: 'account-1',
  status: 'active',
  role: 'rotating',
  welcomeStatus: 'in_progress',
}
vi.mock('@/lib/hooks/useCards', () => ({
  useOwnedCards: () => ({ data: [card], isLoading: false }),
  useUpdateCard: () => ({ mutate, isPending: false }),
}))
beforeEach(() => {
  mutate.mockReset()
  card.welcomeStatus = 'in_progress'
})

it('separates bonus facts from account closure and keeps options open', async () => {
  const user = userEvent.setup()
  const target = {
    kind: 'registered' as const,
    id: 'account-1',
    label: 'Sapphire 8054',
    accountType: 'credit_card',
  }
  const view = render(<HomeAccountOptions target={target} />)
  expect(
    screen.queryByRole('button', { name: 'Bonus received' }),
  ).not.toBeInTheDocument()
  await user.click(screen.getByText('Account options'))
  fireEvent.click(
    await screen.findByRole('button', { name: 'Spending requirement met' }),
  )
  expect(mutate).toHaveBeenLastCalledWith({
    cardId: 'card-1',
    payload: { welcomeStatus: 'spend_met' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Bonus received' }))
  expect(mutate).toHaveBeenLastCalledWith({
    cardId: 'card-1',
    payload: { welcomeStatus: 'earned' },
  })
  card.welcomeStatus = 'earned'
  view.rerender(<HomeAccountOptions target={target} />)
  expect(
    screen.getByText(/Bonus received. You can direct new spending/),
  ).toBeVisible()
  expect(
    screen.getByRole('button', { name: 'Record account closed' }),
  ).toBeVisible()
  expect(
    screen.getByRole('link', { name: 'Card history and rotation plan' }),
  ).toHaveAttribute('href', '/money?tab=cards#card-card-1')
})
