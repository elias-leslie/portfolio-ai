'use client'

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

export type Capture = {
  id: string
  captured_by_name: string
  kind: 'receipt' | 'shelf_tag'
  store_name: string
  note: string
  status: string
  outcome: string
  purchased_by: string | null
  purchased_for: string | null
  document_id: string | null
  review_note: string
  created_at: string
}

/** Statuses the review select offers; mirrors the backend CaptureReview model. */
const REVIEW_STATUSES = ['verified', 'needs_correction', 'pending_review']

/** Start from the capture's own status; `in_review` is not a reviewer choice. */
export function initialReviewStatus(status: string): string {
  return REVIEW_STATUSES.includes(status) ? status : 'pending_review'
}

export function buildCaptureReviewPayload({
  status,
  outcome,
  note,
  buyer,
  beneficiary,
}: {
  status: string
  outcome: string
  note: string
  buyer: string
  beneficiary: string
}) {
  return {
    status,
    outcome,
    review_note: note,
    purchased_by: buyer || null,
    purchased_for: beneficiary || null,
  }
}

/** Prefer the backend's detail (string or FastAPI 422 list) over a generic message. */
export async function captureReviewErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const body: unknown = await response.json()
    const detail =
      body && typeof body === 'object' && 'detail' in body
        ? body.detail
        : undefined
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item: unknown) =>
          item && typeof item === 'object' && 'msg' in item
            ? String(item.msg)
            : '',
        )
        .filter(Boolean)
      if (messages.length) return messages.join(' ')
    }
  } catch {
    // Non-JSON error body: keep the fallback.
  }
  return fallback
}

export function CaptureReviewForm({
  capture,
  onSaved,
}: {
  capture: Capture
  onSaved: () => void
}) {
  const [note, setNote] = useState(capture.review_note)
  const [outcome, setOutcome] = useState(capture.outcome)
  const [status, setStatus] = useState(initialReviewStatus(capture.status))
  const [buyer, setBuyer] = useState(capture.purchased_by ?? '')
  const [beneficiary, setBeneficiary] = useState(capture.purchased_for ?? '')
  const members = useQuery({
    queryKey: ['capture-review-members'],
    queryFn: async (): Promise<{ id: string; name: string }[]> => {
      const response = await fetch('/api/captures/members')
      if (!response.ok) throw new Error('Could not load household members.')
      return response.json()
    },
  })
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  async function save() {
    setSaving(true)
    try {
      const response = await fetch(`/api/captures/${capture.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          buildCaptureReviewPayload({
            status,
            outcome,
            note,
            buyer,
            beneficiary,
          }),
        ),
      })
      if (!response.ok)
        throw new Error(
          await captureReviewErrorMessage(
            response,
            'Review could not be saved. Add a note and retry.',
          ),
        )
      onSaved()
      setMessage(
        'Review saved. This does not add spending or establish a comparable unit price.',
      )
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : 'Unable to save review.',
      )
    } finally {
      setSaving(false)
    }
  }
  return (
    <details className="text-sm">
      <summary className="cursor-pointer py-2">Review this capture</summary>
      <div className="space-y-3 pt-2">
        <label className="block">
          Evidence status
          <select
            className="ml-2 rounded border border-border bg-bg p-2"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="verified">Reviewed</option>
            <option value="needs_correction">Correction needed</option>
            <option value="pending_review">Still awaiting review</option>
          </select>
        </label>
        <label className="block">
          Purchase outcome
          <select
            className="ml-2 rounded border border-border bg-bg p-2"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
          >
            <option value="unknown">Not established</option>
            <option value="purchased">Confirmed purchased</option>
            <option value="not_purchased">Confirmed not purchased</option>
          </select>
        </label>
        <label className="block">
          Purchased by
          <select
            className="ml-2 rounded border border-border bg-bg p-2"
            value={buyer}
            onChange={(e) => setBuyer(e.target.value)}
          >
            <option value="">Unknown</option>
            {members.data?.map((member) => (
              <option key={member.id} value={member.id}>
                {member.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          Purchased for
          <select
            className="ml-2 rounded border border-border bg-bg p-2"
            value={beneficiary}
            onChange={(e) => setBeneficiary(e.target.value)}
          >
            <option value="">Unknown / not specified</option>
            {members.data?.map((member) => (
              <option key={member.id} value={member.id}>
                {member.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          What was checked?
          <textarea
            className="mt-1 w-full rounded border border-border bg-bg p-2"
            maxLength={1000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        <p className="text-xs text-text-muted">
          No matched purchase is an unknown outcome. Confirm only what the
          evidence or the person establishes.
        </p>
        <Button
          size="sm"
          disabled={!note.trim() || saving}
          onClick={() => void save()}
        >
          {saving ? 'Saving…' : 'Save review'}
        </Button>
        {message && <p role="status">{message}</p>}
      </div>
    </details>
  )
}
