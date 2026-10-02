'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useUploadHouseholdDocument,
  useUploadHouseholdDocuments,
} from './useHousehold'

const { toastErrorMock, toastInfoMock, toastSuccessMock } = vi.hoisted(() => ({
  toastErrorMock: vi.fn(),
  toastInfoMock: vi.fn(),
  toastSuccessMock: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    error: toastErrorMock,
    info: toastInfoMock,
    success: toastSuccessMock,
  },
}))

const fetchMock = vi.fn<typeof fetch>()

// These are wire responses. The real API client must normalize every nested key.
function documentFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 'synthetic-document',
    filename: 'synthetic-evidence.csv',
    source_type: 'retirement',
    document_type: 'retirement_statement',
    status: 'staged',
    account_label: 'Synthetic IRA',
    file_size_bytes: 10,
    content_type: 'text/csv',
    classification_confidence: 0.95,
    review_status: null,
    review_summary: null,
    review_confidence: null,
    statement_start: null,
    statement_end: null,
    uploaded_at: '2026-05-02T20:00:00Z',
    parsed_at: null,
    metadata: {},
    ...overrides,
  }
}

function respondWithJson(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    headers: { 'content-type': 'application/json' },
  })
}

function wrapper(queryClient: QueryClient) {
  return function HookWrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
  }
}

function queryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

const uploadPayload = {
  rawText: 'Synthetic account evidence',
  filename: 'synthetic-evidence.csv',
}

async function advanceReviewPoll() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1500)
  })
}

describe('household evidence upload through the real API client', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    toastErrorMock.mockReset()
    toastInfoMock.mockReset()
    toastSuccessMock.mockReset()
  })

  afterEach(() => {
    cleanup()
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('observes applied metadata even before the top-level status completes', async () => {
    fetchMock
      .mockResolvedValueOnce(respondWithJson(documentFixture()))
      .mockResolvedValueOnce(
        respondWithJson({
          items: [
            documentFixture({
              metadata: { application_summary: { status: 'applied' } },
            }),
          ],
        }),
      )
    const client = queryClient()
    const invalidateQueries = vi.spyOn(client, 'invalidateQueries')
    const { result } = renderHook(() => useUploadHouseholdDocument(), {
      wrapper: wrapper(client),
    })

    await act(async () => {
      await result.current.mutateAsync(uploadPayload)
    })
    await advanceReviewPoll()
    await advanceReviewPoll()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/intake/evidence',
      expect.objectContaining({ method: 'POST', body: expect.any(FormData) }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/intake/evidence',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['household'],
      exact: false,
    })
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv applied to money views.',
    )
  })

  it('reports a plain duplicate without staging or polling it', async () => {
    fetchMock.mockResolvedValueOnce(
      respondWithJson(
        documentFixture({ metadata: { duplicate_detected: true } }),
      ),
    )
    const { result } = renderHook(() => useUploadHouseholdDocument(), {
      wrapper: wrapper(queryClient()),
    })

    await act(async () => {
      await result.current.mutateAsync(uploadPayload)
    })
    await advanceReviewPoll()

    expect(toastInfoMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv already exists in evidence intake.',
    )
    expect(toastSuccessMock).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['single', false],
    ['single', true],
    ['batch', false],
    ['batch', true],
  ] as const)('acknowledges %s uploads before household refresh completes (duplicate=%s)', async (mode, duplicate) => {
    const document = documentFixture({
      metadata: duplicate
        ? { duplicate_detected: true }
        : { application_summary: { status: 'needs_review' } },
    })
    fetchMock.mockResolvedValueOnce(
      respondWithJson(mode === 'single' ? document : [document]),
    )
    let releaseRefresh = () => {}
    const refresh = new Promise<void>((resolve) => {
      releaseRefresh = resolve
    })
    const client = queryClient()
    vi.spyOn(client, 'invalidateQueries').mockReturnValue(refresh)
    const { result } = renderHook(
      () => ({
        single: useUploadHouseholdDocument(),
        batch: useUploadHouseholdDocuments(),
      }),
      { wrapper: wrapper(client) },
    )
    let upload: Promise<unknown> | undefined

    await act(async () => {
      upload =
        mode === 'single'
          ? result.current.single.mutateAsync(uploadPayload)
          : result.current.batch.mutateAsync([uploadPayload])
      await vi.advanceTimersByTimeAsync(0)
    })
    try {
      if (duplicate) expect(toastInfoMock).toHaveBeenCalledTimes(1)
      else expect(toastSuccessMock).toHaveBeenCalledTimes(1)
    } finally {
      await act(async () => {
        releaseRefresh()
        await upload
      })
    }
  })

  it('keeps watching a duplicate rebound to another account until it applies', async () => {
    const rebound = {
      duplicate_detected: true,
      duplicate_rebound: true,
      duplicate_rebound_at: '2026-05-02T20:00:02Z',
    }
    fetchMock
      .mockResolvedValueOnce(
        respondWithJson(documentFixture({ metadata: rebound })),
      )
      .mockResolvedValueOnce(
        respondWithJson({
          items: [
            documentFixture({
              metadata: {
                ...rebound,
                application_summary_updated_at: '2026-05-02T20:00:04Z',
                application_summary: { status: 'applied' },
              },
            }),
          ],
        }),
      )
    const { result } = renderHook(() => useUploadHouseholdDocument(), {
      wrapper: wrapper(queryClient()),
    })

    await act(async () => {
      await result.current.mutateAsync({
        ...uploadPayload,
        householdAccountId: 'synthetic-account',
      })
    })
    await advanceReviewPoll()
    await advanceReviewPoll()

    expect(toastSuccessMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv already exists; reapplying to selected account.',
    )
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv applied to money views.',
    )
    expect(toastInfoMock).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('does not mistake the prior applied review for rebound completion', async () => {
    const metadata = {
      duplicate_detected: true,
      duplicate_rebound: true,
      duplicate_rebound_at: '2026-05-02T20:00:02Z',
      application_summary: { status: 'applied' },
    }
    const oldReview = documentFixture({
      status: 'parsed',
      review_status: 'complete',
      parsed_at: '2026-05-02T20:00:01Z',
      metadata,
    })
    const parsingReview = { ...oldReview, parsed_at: '2026-05-02T20:00:03Z' }
    const newReview = {
      ...parsingReview,
      metadata: {
        ...metadata,
        application_summary_updated_at: '2026-05-02T20:00:04Z',
      },
    }
    fetchMock
      .mockResolvedValueOnce(respondWithJson(oldReview))
      .mockResolvedValueOnce(respondWithJson({ items: [parsingReview] }))
      .mockResolvedValueOnce(respondWithJson({ items: [newReview] }))
    const { result } = renderHook(() => useUploadHouseholdDocument(), {
      wrapper: wrapper(queryClient()),
    })

    await act(async () => {
      await result.current.mutateAsync(uploadPayload)
    })
    await advanceReviewPoll()
    expect(toastSuccessMock).toHaveBeenCalledTimes(1)
    await advanceReviewPoll()
    await advanceReviewPoll()

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv applied to money views.',
    )
  })

  it.each([
    'single',
    'batch',
  ] as const)('does not announce old rebound success after %s polling expires', async (mode) => {
    const oldReview = documentFixture({
      status: 'parsed',
      review_status: 'complete',
      parsed_at: '2026-05-02T20:00:03Z',
      metadata: {
        duplicate_detected: true,
        duplicate_rebound: true,
        duplicate_rebound_at: '2026-05-02T20:00:02Z',
        application_summary: { status: 'applied' },
        application_summary_updated_at: '2026-05-02T20:00:01Z',
      },
    })
    fetchMock
      .mockResolvedValueOnce(
        respondWithJson(mode === 'single' ? oldReview : [oldReview]),
      )
      .mockImplementation(async () => respondWithJson({ items: [oldReview] }))
    const { result } = renderHook(
      () => ({
        single: useUploadHouseholdDocument(),
        batch: useUploadHouseholdDocuments(),
      }),
      { wrapper: wrapper(queryClient()) },
    )

    await act(async () => {
      if (mode === 'single')
        await result.current.single.mutateAsync(uploadPayload)
      else await result.current.batch.mutateAsync([uploadPayload])
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(41)
    expect(toastSuccessMock).toHaveBeenCalledTimes(1)
    expect(toastSuccessMock).not.toHaveBeenCalledWith(
      'synthetic-evidence.csv applied to money views.',
    )
  })

  it('keeps watching parsed evidence until the application summary arrives', async () => {
    const parsed = documentFixture({
      status: 'parsed',
      review_status: 'complete',
    })
    fetchMock
      .mockResolvedValueOnce(respondWithJson(parsed))
      .mockResolvedValueOnce(respondWithJson({ items: [parsed] }))
      .mockResolvedValueOnce(
        respondWithJson({
          items: [
            {
              ...parsed,
              metadata: { application_summary: { status: 'applied' } },
            },
          ],
        }),
      )
    const { result } = renderHook(() => useUploadHouseholdDocument(), {
      wrapper: wrapper(queryClient()),
    })

    await act(async () => {
      await result.current.mutateAsync(uploadPayload)
    })
    await advanceReviewPoll()
    expect(toastSuccessMock).toHaveBeenCalledTimes(1)
    await advanceReviewPoll()

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv applied to money views.',
    )
  })

  it('reports a new rebound review failure without accepting the old applied summary', async () => {
    const metadata = {
      duplicate_detected: true,
      duplicate_rebound: true,
      duplicate_rebound_at: '2026-05-02T20:00:02Z',
      application_summary: { status: 'applied' },
    }
    fetchMock
      .mockResolvedValueOnce(respondWithJson(documentFixture({ metadata })))
      .mockResolvedValueOnce(
        respondWithJson({
          items: [
            documentFixture({
              status: 'needs_review',
              review_status: 'failed',
              parsed_at: '2026-05-02T20:00:03Z',
              metadata,
            }),
          ],
        }),
      )
    const { result } = renderHook(() => useUploadHouseholdDocument(), {
      wrapper: wrapper(queryClient()),
    })

    await act(async () => {
      await result.current.mutateAsync(uploadPayload)
    })
    await advanceReviewPoll()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(toastErrorMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv evidence review failed.',
    )
    expect(toastSuccessMock).toHaveBeenCalledTimes(1)
  })

  it('stops watching a needs-review outcome without claiming it applied', async () => {
    fetchMock
      .mockResolvedValueOnce(respondWithJson(documentFixture()))
      .mockResolvedValueOnce(
        respondWithJson({
          items: [
            documentFixture({
              metadata: { application_summary: { status: 'needs_review' } },
            }),
          ],
        }),
      )
    const { result } = renderHook(() => useUploadHouseholdDocument(), {
      wrapper: wrapper(queryClient()),
    })

    await act(async () => {
      await result.current.mutateAsync(uploadPayload)
    })
    await advanceReviewPoll()
    await advanceReviewPoll()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(toastSuccessMock).toHaveBeenCalledTimes(1)
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv staged for evidence intake.',
    )
  })

  it('retains review failure feedback', async () => {
    fetchMock
      .mockResolvedValueOnce(respondWithJson(documentFixture()))
      .mockResolvedValueOnce(
        respondWithJson({ items: [documentFixture({ status: 'failed' })] }),
      )
    const { result } = renderHook(() => useUploadHouseholdDocument(), {
      wrapper: wrapper(queryClient()),
    })

    await act(async () => {
      await result.current.mutateAsync(uploadPayload)
    })
    await advanceReviewPoll()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(toastErrorMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv evidence review failed.',
    )
    expect(toastSuccessMock).toHaveBeenCalledTimes(1)
  })

  it('reports an all-duplicate batch without polling', async () => {
    fetchMock.mockResolvedValueOnce(
      respondWithJson([
        documentFixture({ metadata: { duplicate_detected: true } }),
      ]),
    )
    const { result } = renderHook(() => useUploadHouseholdDocuments(), {
      wrapper: wrapper(queryClient()),
    })

    await act(async () => {
      await result.current.mutateAsync([uploadPayload])
    })
    await advanceReviewPoll()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/intake/evidence/batch',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(toastInfoMock).toHaveBeenCalledWith(
      'Evidence files already exist in intake.',
    )
    expect(toastSuccessMock).not.toHaveBeenCalled()
  })

  it('watches new and rebound batch documents while excluding plain duplicates', async () => {
    const duplicate = documentFixture({
      id: 'synthetic-duplicate',
      metadata: { duplicate_detected: true },
    })
    const rebound = documentFixture({
      id: 'synthetic-rebound',
      filename: 'synthetic-rebound.csv',
      metadata: {
        duplicate_detected: true,
        duplicate_rebound: true,
        duplicate_rebound_at: '2026-05-02T20:00:02Z',
      },
    })
    const staged = documentFixture()
    const applied = [staged, rebound].map((document) => ({
      ...document,
      metadata: {
        ...document.metadata,
        application_summary_updated_at: '2026-05-02T20:00:04Z',
        application_summary: { status: 'applied' },
      },
    }))
    fetchMock
      .mockResolvedValueOnce(respondWithJson([duplicate, staged, rebound]))
      .mockImplementation(async () =>
        respondWithJson({ items: [duplicate, ...applied] }),
      )
    const { result } = renderHook(() => useUploadHouseholdDocuments(), {
      wrapper: wrapper(queryClient()),
    })

    await act(async () => {
      await result.current.mutateAsync([
        uploadPayload,
        uploadPayload,
        uploadPayload,
      ])
    })
    await advanceReviewPoll()
    await advanceReviewPoll()

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(toastSuccessMock).toHaveBeenCalledWith(
      '2 evidence files staged for intake.',
    )
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'synthetic-evidence.csv applied to money views.',
    )
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'synthetic-rebound.csv applied to money views.',
    )
    expect(toastSuccessMock).toHaveBeenCalledTimes(3)
  })
})
