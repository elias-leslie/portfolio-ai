import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useExchangePlaidPublicToken, useSyncPlaidItems } from './usePlaid'

const { syncMock, exchangeMock, successMock, warningMock, errorMock } =
  vi.hoisted(() => ({
    syncMock: vi.fn(),
    exchangeMock: vi.fn(),
    successMock: vi.fn(),
    warningMock: vi.fn(),
    errorMock: vi.fn(),
  }))
vi.mock('@/lib/api/plaid', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api/plaid')>()),
  configurePlaid: vi.fn(),
  createPlaidLinkToken: vi.fn(),
  exchangePlaidPublicToken: exchangeMock,
  fetchPlaidStatus: vi.fn(),
  removePlaidItem: vi.fn(),
  syncPlaidItems: syncMock,
}))
vi.mock('sonner', () => ({
  toast: { success: successMock, warning: warningMock, error: errorMock },
}))

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { mutations: { retry: false } } })
      }
    >
      {children}
    </QueryClientProvider>
  )
}

describe('Plaid sync notices', () => {
  beforeEach(() => vi.clearAllMocks())

  it('warns about partial sync errors and preserves provider detail', async () => {
    syncMock.mockResolvedValue({
      errors: [{ errorMessage: 'Transactions unavailable' }],
    })
    const { result } = renderHook(() => useSyncPlaidItems(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({})
    })
    expect(warningMock).toHaveBeenCalledWith(
      'Plaid sync finished with 1 issue.',
      { description: 'Transactions unavailable' },
    )
    expect(successMock).not.toHaveBeenCalled()
  })

  it('reports connected-but-not-synced after token exchange', async () => {
    exchangeMock.mockResolvedValue({
      itemId: 'item-1',
      sync: { errors: [{ detail: 'Transactions unavailable' }] },
    })
    const { result } = renderHook(() => useExchangePlaidPublicToken(), {
      wrapper,
    })
    await act(async () => {
      await result.current.mutateAsync({ publicToken: 'test' })
    })
    expect(warningMock).toHaveBeenCalledWith(
      'Plaid account linked; sync has 1 issue.',
      { description: 'Transactions unavailable' },
    )
    expect(successMock).not.toHaveBeenCalled()
  })

  it('keeps success for a complete sync', async () => {
    syncMock.mockResolvedValue({ errors: [] })
    const { result } = renderHook(() => useSyncPlaidItems(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({})
    })
    expect(successMock).toHaveBeenCalledWith('Plaid sync finished.')
    expect(warningMock).not.toHaveBeenCalled()
  })

  it('refreshes household and retirement queries after a sync', async () => {
    syncMock.mockResolvedValue({ errors: [] })
    const client = new QueryClient()
    client.setQueryData(['household', 'dashboard'], { ok: true })
    client.setQueryData(['retirement', 'spending-actuals'], { ok: true })
    client.setQueryData(['portfolio', 'summary'], { ok: true })
    const { result } = renderHook(() => useSyncPlaidItems(), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    })
    await act(async () => {
      await result.current.mutateAsync({})
    })
    const invalidated = (key: string[]) =>
      client.getQueryState(key)?.isInvalidated
    expect(invalidated(['household', 'dashboard'])).toBe(true)
    expect(invalidated(['retirement', 'spending-actuals'])).toBe(true)
    expect(invalidated(['portfolio', 'summary'])).toBe(false)
  })
})
