'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { SnapTradeSyncResult } from '@/lib/api/snaptrade'
import { useSyncSnapTrade } from './useSnapTrade'

const {
  syncSnapTradeMock,
  toastErrorMock,
  toastSuccessMock,
  toastWarningMock,
} = vi.hoisted(() => ({
  syncSnapTradeMock: vi.fn(),
  toastErrorMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastWarningMock: vi.fn(),
}))

vi.mock('@/lib/api/snaptrade', () => ({
  configureSnapTrade: vi.fn(),
  createSnapTradeConnectionPortal: vi.fn(),
  fetchSnapTradeOrders: vi.fn(),
  fetchSnapTradeStatus: vi.fn(),
  syncSnapTrade: syncSnapTradeMock,
}))

vi.mock('sonner', () => ({
  toast: {
    error: toastErrorMock,
    success: toastSuccessMock,
    warning: toastWarningMock,
  },
}))

function buildSyncResult(
  overrides: Partial<SnapTradeSyncResult> = {},
): SnapTradeSyncResult {
  return {
    status: 'success',
    connectionCount: 1,
    accountCount: 2,
    positionCount: 8,
    activityCount: 4,
    orderCount: 1,
    portfolioAccountCount: 2,
    portfolioPositionCount: 8,
    errorCount: 0,
    errors: [],
    ...overrides,
  }
}

function wrapper(queryClient: QueryClient) {
  return function HookWrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
  }
}

describe('useSyncSnapTrade', () => {
  beforeEach(() => {
    syncSnapTradeMock.mockReset()
    toastErrorMock.mockReset()
    toastSuccessMock.mockReset()
    toastWarningMock.mockReset()
  })

  it.each([
    ['partial status', buildSyncResult({ status: 'partial' })],
    ['reported errors', buildSyncResult({ errorCount: 1 })],
  ])('warns instead of claiming success for %s', async (_case, syncResult) => {
    syncSnapTradeMock.mockResolvedValue(syncResult)
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    })
    const { result } = renderHook(() => useSyncSnapTrade(), {
      wrapper: wrapper(queryClient),
    })

    await act(async () => {
      await result.current.mutateAsync()
    })

    expect(toastWarningMock).toHaveBeenCalledWith(
      'SnapTrade sync finished with 1 issue.',
      { description: 'Some brokerage data could not be refreshed.' },
    )
    expect(toastSuccessMock).not.toHaveBeenCalled()
  })

  it('summarizes the first provider error without hiding additional issues', async () => {
    syncSnapTradeMock.mockResolvedValue(
      buildSyncResult({
        status: 'partial',
        errorCount: 2,
        errors: [
          {
            surface: 'positions',
            errorMessage: 'Position snapshot was unavailable.',
          },
          {
            surface: 'orders',
            errorMessage: 'Order snapshot was unavailable.',
          },
        ],
      }),
    )
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    })
    const { result } = renderHook(() => useSyncSnapTrade(), {
      wrapper: wrapper(queryClient),
    })

    await act(async () => {
      await result.current.mutateAsync()
    })

    expect(toastWarningMock).toHaveBeenCalledWith(
      'SnapTrade sync finished with 2 issues.',
      {
        description: 'positions: Position snapshot was unavailable. (+1 more)',
      },
    )
    expect(toastSuccessMock).not.toHaveBeenCalled()
  })

  it('keeps the success toast for a complete sync', async () => {
    syncSnapTradeMock.mockResolvedValue(buildSyncResult())
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    })
    const { result } = renderHook(() => useSyncSnapTrade(), {
      wrapper: wrapper(queryClient),
    })

    await act(async () => {
      await result.current.mutateAsync()
    })

    expect(toastSuccessMock).toHaveBeenCalledWith('SnapTrade sync finished.')
    expect(toastWarningMock).not.toHaveBeenCalled()
  })
})
