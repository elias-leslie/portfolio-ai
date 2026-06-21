'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useUploadHouseholdDocument } from './useHousehold'

const {
  fetchHouseholdDocumentsMock,
  toastErrorMock,
  toastInfoMock,
  toastSuccessMock,
  uploadHouseholdDocumentMock,
} = vi.hoisted(() => ({
  fetchHouseholdDocumentsMock: vi.fn(),
  toastErrorMock: vi.fn(),
  toastInfoMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  uploadHouseholdDocumentMock: vi.fn(),
}))

vi.mock('@/lib/api/household', () => ({
  answerHouseholdQuestion: vi.fn(),
  askJenny: vi.fn(),
  categorizeHouseholdTransaction: vi.fn(),
  confirmFact: vi.fn(),
  createHouseholdTrackedAccount: vi.fn(),
  deleteHouseholdTrackedAccount: vi.fn(),
  fetchConfirmedFacts: vi.fn(),
  fetchHouseholdDashboard: vi.fn(),
  fetchHouseholdDocuments: fetchHouseholdDocumentsMock,
  fetchHouseholdLedger: vi.fn(),
  fetchHouseholdSpending: vi.fn(),
  updateHouseholdPlanning: vi.fn(),
  updateHouseholdProfile: vi.fn(),
  updateHouseholdTrackedAccount: vi.fn(),
  uploadHouseholdDocument: uploadHouseholdDocumentMock,
}))

vi.mock('sonner', () => ({
  toast: {
    error: toastErrorMock,
    info: toastInfoMock,
    success: toastSuccessMock,
  },
}))

function documentFixture(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id: 'doc-positions',
    filename: 'Portfolio_Positions_May-02-2026.csv',
    sourceType: 'retirement',
    documentType: 'retirement_statement',
    status: 'staged',
    accountLabel: 'Traditional IRA',
    fileSizeBytes: 10,
    contentType: 'text/csv',
    classificationConfidence: 0.95,
    reviewStatus: null,
    reviewSummary: null,
    reviewConfidence: null,
    statementStart: null,
    statementEnd: null,
    uploadedAt: '2026-05-02T20:00:00Z',
    parsedAt: null,
    metadata: {},
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

describe('useUploadHouseholdDocument', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    fetchHouseholdDocumentsMock.mockReset()
    toastErrorMock.mockReset()
    toastInfoMock.mockReset()
    toastSuccessMock.mockReset()
    uploadHouseholdDocumentMock.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('polls review completion and refreshes household queries after upload', async () => {
    const stagedDocument = documentFixture()
    const appliedDocument = documentFixture({
      status: 'parsed',
      reviewStatus: 'complete',
      parsedAt: '2026-05-02T20:00:03Z',
      metadata: { application_summary: { status: 'applied' } },
    })
    uploadHouseholdDocumentMock.mockResolvedValue(stagedDocument)
    fetchHouseholdDocumentsMock.mockResolvedValue({ items: [appliedDocument] })
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useUploadHouseholdDocument(), {
      wrapper: wrapper(queryClient),
    })

    await act(async () => {
      await result.current.mutateAsync({
        rawText: 'Traditional IRA total 368331.51',
        accountLabel: 'Traditional IRA',
        householdAccountId: '6bae56cf-f08d-449b-867a-d85a7517f856',
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })
    await act(async () => {
      await Promise.resolve()
    })

    expect(fetchHouseholdDocumentsMock).toHaveBeenCalled()
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['household'],
      exact: false,
    })
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'Portfolio_Positions_May-02-2026.csv applied to money views.',
    )
  })
})
