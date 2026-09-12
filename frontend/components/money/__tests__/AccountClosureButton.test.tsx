import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { recordAccountClosed } from '@/lib/api/household/account-lifecycle'
import { AccountClosureButton } from '../AccountClosureButton'

vi.mock('@/lib/api/household/account-lifecycle', () => ({
  recordAccountClosed: vi.fn(),
}))
const target = {
  kind: 'discovered' as const,
  id: 'unlinked_4635',
  label: 'Visa 4635',
}
beforeEach(() => vi.resetAllMocks())

it('requires an explicit closure confirmation, preserves unknown dates and refreshes all affected views', async () => {
  vi.mocked(recordAccountClosed).mockResolvedValue({
    accountId: 'canonical',
    label: 'Visa 4635',
    status: 'closed',
  })
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  render(
    <QueryClientProvider client={client}>
      <AccountClosureButton target={target} />
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Already closed' }))
  expect(recordAccountClosed).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Save closed account' }))
  await waitFor(() =>
    expect(recordAccountClosed).toHaveBeenCalledWith(target, null),
  )
  await waitFor(() =>
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['home'] }),
  )
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['household'] })
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['cards'] })
})

it('keeps a failed closure open for retry and lets the user cancel without saving', async () => {
  vi.mocked(recordAccountClosed).mockRejectedValue(
    new Error('Account changed; refresh first.'),
  )
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AccountClosureButton target={target} />
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Already closed' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save closed account' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Account changed')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(
    screen.queryByRole('button', { name: 'Save closed account' }),
  ).not.toBeInTheDocument()
  expect(recordAccountClosed).toHaveBeenCalledTimes(1)
})
