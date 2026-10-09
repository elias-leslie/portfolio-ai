import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { type Capture, CaptureReviewForm } from './CaptureReviewForm'

afterEach(() => vi.unstubAllGlobals())

const capture: Capture = {
  id: 'cap-1',
  captured_by_name: 'Test adult',
  kind: 'receipt',
  store_name: 'Test store',
  note: '',
  status: 'needs_correction',
  outcome: 'purchased',
  purchased_by: 'member-a',
  purchased_for: null,
  document_id: null,
  review_note: '',
  created_at: '2026-01-01T00:00:00Z',
}

function renderForm(patchResponse: {
  ok: boolean
  status?: number
  body?: unknown
}) {
  const patches: { url: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/api/captures/members')
        return {
          ok: true,
          json: async () => [
            { id: 'member-a', name: 'Adult A' },
            { id: 'member-b', name: 'Adult B' },
          ],
        }
      patches.push({ url, body: JSON.parse(String(init?.body)) })
      return {
        ok: patchResponse.ok,
        status: patchResponse.status ?? 200,
        json: async () => patchResponse.body ?? {},
      }
    }),
  )
  const onSaved = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CaptureReviewForm capture={capture} onSaved={onSaved} />
    </QueryClientProvider>,
  )
  return { patches, onSaved }
}

describe('CaptureReviewForm', () => {
  it('starts from the capture status and sends buyer and beneficiary', async () => {
    const { patches, onSaved } = renderForm({ ok: true })
    const status = screen.getByLabelText(
      /^Evidence status/,
    ) as HTMLSelectElement
    expect(status.value).toBe('needs_correction')
    await screen.findAllByRole('option', { name: 'Adult B' })
    fireEvent.change(screen.getByLabelText(/^Purchased for/), {
      target: { value: 'member-b' },
    })
    fireEvent.change(screen.getByLabelText(/^What was checked/), {
      target: { value: 'Matched card statement' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save review' }))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(patches).toEqual([
      {
        url: '/api/captures/cap-1',
        body: {
          status: 'needs_correction',
          outcome: 'purchased',
          review_note: 'Matched card statement',
          purchased_by: 'member-a',
          purchased_for: 'member-b',
        },
      },
    ])
  })

  it('shows the backend 422 detail when the save is rejected', async () => {
    renderForm({
      ok: false,
      status: 422,
      body: { detail: [{ msg: 'Input should be a valid UUID' }] },
    })
    fireEvent.change(screen.getByLabelText(/^What was checked/), {
      target: { value: 'Checked' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save review' }))
    expect(
      await screen.findByText('Input should be a valid UUID'),
    ).toBeInTheDocument()
  })
})
