'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ShoppingPilot } from '@/components/capture/ShoppingPilot'
import { useHouseholdIdentity } from '@/components/providers/HouseholdIdentityProvider'
import { Button } from '@/components/ui/button'
import {
  type CaptureDraft,
  listCaptureDrafts,
  removeCaptureDraft,
  saveCaptureDraft,
  uploadCaptureDraft,
} from '@/lib/capture-drafts'

type Capture = {
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

async function readCaptures(): Promise<Capture[]> {
  const response = await fetch('/api/captures', { cache: 'no-store' })
  if (!response.ok)
    throw new Error(
      'Uploads could not be loaded. Your saved drafts are still below.',
    )
  const value: unknown = await response.json()
  if (
    !Array.isArray(value) ||
    !value.every(
      (row: unknown) =>
        typeof row === 'object' &&
        row !== null &&
        'id' in row &&
        typeof row.id === 'string' &&
        'kind' in row &&
        'status' in row,
    )
  )
    throw new Error('Uploads could not be read.')
  return value as Capture[]
}

export default function CapturePage() {
  const identity = useHouseholdIdentity()
  const member = identity.member_id ?? 'local'
  const adult = identity.access !== 'capture_only'
  const [kind, setKind] = useState<'receipt' | 'shelf_tag'>('receipt')
  const [store, setStore] = useState('')
  const [note, setNote] = useState('')
  const [drafts, setDrafts] = useState<CaptureDraft[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const uploading = useRef(false)
  const input = useRef<HTMLInputElement>(null)
  const captures = useQuery({
    queryKey: ['captures', member],
    queryFn: readCaptures,
    refetchInterval: (query) =>
      query.state.data?.some((capture) => capture.status === 'in_review')
        ? 5000
        : false,
  })
  const refreshDrafts = useCallback(async () => {
    setDrafts(await listCaptureDrafts(member))
  }, [member])
  useEffect(() => {
    void refreshDrafts().catch((error: Error) => setMessage(error.message))
  }, [refreshDrafts])

  async function queue(file: File) {
    if (file.size > 15 * 1024 * 1024) {
      setMessage('Choose a photo or receipt smaller than 15 MB.')
      return
    }
    setBusy('saving')
    try {
      const draft: CaptureDraft = {
        id: crypto.randomUUID(),
        member,
        kind,
        file,
        filename: file.name,
        storeName: store,
        note,
        createdAt: Date.now(),
      }
      await saveCaptureDraft(draft)
      await refreshDrafts()
      setMessage(
        'Saved on this device. Upload when connected; you can close this page meanwhile.',
      )
      if (input.current) input.current.value = ''
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'Unable to save. Keep the original photo.',
      )
    } finally {
      setBusy(null)
    }
  }

  async function upload(draft: CaptureDraft) {
    if (uploading.current) return
    uploading.current = true
    setBusy(draft.id)
    try {
      await uploadCaptureDraft(draft)
      setMessage('Uploaded. Awaiting review; no spending has been added.')
      await captures.refetch()
    } catch (error) {
      const text =
        error instanceof Error
          ? error.message
          : 'Upload failed. Draft retained.'
      await saveCaptureDraft({ ...draft, error: text }).catch(() => undefined)
      setMessage(text)
    } finally {
      uploading.current = false
      setBusy(null)
      await refreshDrafts()
    }
  }

  async function toIntake(capture: Capture) {
    setBusy(capture.id)
    try {
      const response = await fetch(`/api/captures/${capture.id}/intake`, {
        method: 'POST',
      })
      if (!response.ok)
        throw new Error(
          'Could not send to Intake. The uploaded capture is still saved; retry.',
        )
      await captures.refetch()
      setMessage(
        'Sent to Intake for extraction and review. Confirm proposed changes there.',
      )
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : 'Could not send to Intake.',
      )
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-semibold">
          Capture a receipt or shelf tag
        </h1>
        <p className="mt-2 text-sm text-text-muted">
          Save evidence now. Review prices and purchases after upload.
        </p>
      </div>
      <section
        className="space-y-4 rounded-xl border border-border bg-surface p-4"
        aria-label="New capture"
      >
        <fieldset className="flex gap-4">
          <legend className="mb-2 text-sm font-medium">
            What are you saving?
          </legend>
          {(['receipt', 'shelf_tag'] as const).map((value) => (
            <label className="flex min-h-11 items-center gap-2" key={value}>
              <input
                type="radio"
                name="capture-kind"
                checked={kind === value}
                onChange={() => setKind(value)}
              />
              {value === 'receipt' ? 'Receipt' : 'Shelf tag'}
            </label>
          ))}
        </fieldset>
        <details>
          <summary className="cursor-pointer py-2 text-sm">
            Add store or note (optional)
          </summary>
          <div className="space-y-3 py-2">
            {' '}
            <label className="block text-sm">
              Store (optional)
              <input
                className="mt-1 block w-full rounded-md border border-border bg-bg p-3"
                value={store}
                maxLength={120}
                onChange={(e) => setStore(e.target.value)}
                placeholder="Store and location"
              />
            </label>
            <label className="block text-sm">
              Note (optional)
              <input
                className="mt-1 block w-full rounded-md border border-border bg-bg p-3"
                value={note}
                maxLength={1000}
                onChange={(e) => setNote(e.target.value)}
                placeholder={
                  kind === 'shelf_tag'
                    ? 'Item number, package size, coupon or member price'
                    : 'Anything the receipt does not show'
                }
              />
            </label>
          </div>
        </details>
        <label className="block text-sm font-medium">
          Take a photo or choose a file
          <input
            ref={input}
            className="mt-2 block w-full min-w-0 rounded-md border border-border p-3 text-sm"
            type="file"
            accept={
              kind === 'receipt'
                ? 'image/jpeg,image/png,image/webp,application/pdf'
                : 'image/jpeg,image/png,image/webp'
            }
            capture="environment"
            disabled={busy !== null}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void queue(file)
            }}
          />
        </label>
        <p className="text-xs text-text-muted">
          Keep the full receipt total or the shelf tag’s item number, size and
          price in view. A capture records {identity.display_name} as the
          contributor; the buyer and intended person remain unknown until
          confirmed.
        </p>
      </section>
      {message && (
        <p
          role="status"
          className="rounded-lg border border-border p-3 text-sm"
        >
          {message}
        </p>
      )}
      <ShoppingPilot />
      <section aria-label="Saved drafts" className="space-y-3">
        <h2 className="text-lg font-semibold">
          Saved on this device {drafts.length > 0 && `(${drafts.length})`}
        </h2>
        {drafts.length === 0 ? (
          <p className="text-sm text-text-muted">No pending drafts.</p>
        ) : (
          drafts.map((draft) => (
            <div
              key={draft.id}
              className="space-y-2 rounded-lg border border-border p-3"
            >
              <p>
                {draft.kind === 'receipt' ? 'Receipt' : 'Shelf tag'} ·{' '}
                {draft.storeName || 'Store not recorded'}
              </p>
              <p className="text-xs text-text-muted">
                {new Date(draft.createdAt).toLocaleString()} ·{' '}
                {draft.error || 'Saved; waiting for upload'}
              </p>
              <DraftPreview draft={draft} />
              <div className="flex gap-2">
                <Button
                  disabled={busy !== null}
                  onClick={() => void upload(draft)}
                >
                  {busy === draft.id
                    ? 'Uploading…'
                    : draft.error
                      ? 'Retry upload'
                      : 'Upload'}
                </Button>
                <Button
                  variant="ghost"
                  disabled={busy !== null}
                  onClick={() => {
                    if (
                      window.confirm(
                        'Discard this draft from this device? It has not been uploaded.',
                      )
                    )
                      void removeCaptureDraft(draft.id).then(refreshDrafts)
                  }}
                >
                  Discard
                </Button>
              </div>
            </div>
          ))
        )}
        {drafts.length > 0 && (
          <p className="text-xs text-text-muted">
            Drafts stay with this sign-in on this browser. Clearing browser
            storage removes them.
          </p>
        )}
      </section>
      <section className="space-y-3" aria-label="Uploaded captures">
        <h2 className="text-lg font-semibold">
          {adult ? 'Family uploads' : 'Your uploads'}
        </h2>
        {captures.isPending && <p role="status">Loading uploads…</p>}
        {captures.isError && (
          <div>
            <p role="alert">{captures.error.message}</p>
            <Button variant="outline" onClick={() => void captures.refetch()}>
              Retry loading
            </Button>
          </div>
        )}
        {captures.data?.length === 0 && (
          <p className="text-sm text-text-muted">No uploaded captures yet.</p>
        )}
        {captures.data?.map((capture) => (
          <article
            key={capture.id}
            className="space-y-2 rounded-lg border border-border p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-medium">
                {capture.store_name || 'Store not recorded'} ·{' '}
                {capture.kind === 'receipt' ? 'Receipt' : 'Shelf tag'}
              </h3>
              <span className="text-xs text-text-muted">
                {capture.status === 'pending_review'
                  ? 'Awaiting review'
                  : capture.status === 'in_review'
                    ? 'In Intake review'
                    : capture.status === 'verified'
                      ? 'Reviewed'
                      : 'Correction needed'}
              </span>
            </div>
            <p className="text-xs text-text-muted">
              Captured by {capture.captured_by_name} ·{' '}
              {new Date(capture.created_at).toLocaleDateString()}
            </p>
            {capture.note && <p className="text-sm">{capture.note}</p>}
            <p className="text-xs text-text-muted">
              Purchase outcome:{' '}
              {capture.outcome === 'unknown'
                ? 'not established'
                : capture.outcome.replaceAll('_', ' ')}
            </p>
            {capture.review_note && (
              <p className="text-sm">{capture.review_note}</p>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <a
                className="text-sm underline"
                href={`/api/captures/${capture.id}/image`}
                target="_blank"
                rel="noreferrer"
              >
                View original
              </a>
              {adult && capture.kind === 'receipt' && !capture.document_id && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy !== null}
                  onClick={() => void toIntake(capture)}
                >
                  Send to Intake review
                </Button>
              )}
              {adult && capture.document_id && (
                <Link
                  className="text-sm underline"
                  href={`/money?tab=intake&document=${capture.document_id}`}
                >
                  Open Intake review
                </Link>
              )}
            </div>
            {adult && (
              <CaptureReviewForm
                capture={capture}
                onSaved={() => void captures.refetch()}
              />
            )}
          </article>
        ))}
      </section>
    </div>
  )
}

function CaptureReviewForm({
  capture,
  onSaved,
}: {
  capture: Capture
  onSaved: () => void
}) {
  const [note, setNote] = useState(capture.review_note)
  const [outcome, setOutcome] = useState(capture.outcome)
  const [status, setStatus] = useState('verified')
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
        body: JSON.stringify({ status, outcome, review_note: note }),
      })
      if (!response.ok)
        throw new Error('Review could not be saved. Add a note and retry.')
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

function DraftPreview({ draft }: { draft: CaptureDraft }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    const preview = URL.createObjectURL(draft.file)
    setUrl(preview)
    return () => URL.revokeObjectURL(preview)
  }, [draft.file])
  return url ? (
    <a
      className="inline-block py-2 text-sm underline"
      href={url}
      target="_blank"
      rel="noreferrer"
    >
      Review photo or file
    </a>
  ) : null
}
