import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { invalidateHouseholdQueries } from './household-query-cache'
import { useCategorizeHouseholdTransaction } from './useHousehold'

vi.mock('@/lib/api/household', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api/household')>()),
  categorizeHouseholdTransaction: vi.fn().mockResolvedValue({}),
}))
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

function seededClient() {
  const client = new QueryClient()
  client.setQueryData(['household', 'ledger'], [])
  client.setQueryData(['retirement', 'preview', {}], {})
  return client
}

const invalidated = (client: QueryClient, key: unknown[]) =>
  client.getQueryState(key)?.isInvalidated

describe('household query invalidation', () => {
  it('leaves retirement queries alone unless asked', async () => {
    const client = seededClient()
    await invalidateHouseholdQueries(client)
    expect(invalidated(client, ['household', 'ledger'])).toBe(true)
    expect(invalidated(client, ['retirement', 'preview', {}])).toBe(false)
  })

  it('refreshes retirement inputs after a ledger edit', async () => {
    const client = seededClient()
    const { result } = renderHook(() => useCategorizeHouseholdTransaction(), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    })
    await act(async () => {
      await result.current.mutateAsync({
        transactionId: 'txn-1',
        category: 'groceries',
        essentiality: 'essential',
      })
    })
    expect(invalidated(client, ['household', 'ledger'])).toBe(true)
    expect(invalidated(client, ['retirement', 'preview', {}])).toBe(true)
  })
})
