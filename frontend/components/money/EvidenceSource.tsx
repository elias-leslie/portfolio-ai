'use client'

import { useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { apiRequest } from '@/lib/api/client'
import { formatCurrency } from '@/lib/formatters'

interface ReceiptArithmetic {
  merchant: string
  readableLines: number
  lineTotal: number | null
  subtotal: number | null
  tax: number | null
  total: number | null
  lineDifference: number | null
  totalDifference: number | null
}
interface EvidenceSourceData {
  reviewId: string | null
  text: string
  truncated: boolean
  questions: string[]
  arithmetic: ReceiptArithmetic[]
}
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Evidence source is unreadable.')
  return value as Record<string, unknown>
}
function numberOrNull(value: unknown): number | null {
  if (value === null) return null
  if (typeof value !== 'number' || !Number.isFinite(value))
    throw new Error('Evidence arithmetic is unreadable.')
  return value
}
export function parseEvidenceSource(value: unknown): EvidenceSourceData {
  const data = record(value)
  if (
    (data.reviewId !== null && typeof data.reviewId !== 'string') ||
    typeof data.text !== 'string' ||
    typeof data.truncated !== 'boolean' ||
    !Array.isArray(data.questions) ||
    !data.questions.every((q) => typeof q === 'string') ||
    !Array.isArray(data.arithmetic)
  )
    throw new Error('Evidence source is unreadable.')
  return {
    reviewId: data.reviewId,
    text: data.text,
    truncated: data.truncated,
    questions: data.questions,
    arithmetic: data.arithmetic.map((item) => {
      const row = record(item)
      if (
        typeof row.merchant !== 'string' ||
        typeof row.readableLines !== 'number' ||
        !Number.isInteger(row.readableLines) ||
        row.readableLines < 0
      )
        throw new Error('Evidence arithmetic is unreadable.')
      return {
        merchant: row.merchant,
        readableLines: row.readableLines,
        lineTotal: numberOrNull(row.lineTotal),
        subtotal: numberOrNull(row.subtotal),
        tax: numberOrNull(row.tax),
        total: numberOrNull(row.total),
        lineDifference: numberOrNull(row.lineDifference),
        totalDifference: numberOrNull(row.totalDifference),
      }
    }),
  }
}
const amount = (value: number | null) =>
  value === null ? 'Not extracted' : formatCurrency(value)
export function EvidenceSource({
  documentId,
  reviewId,
  fileAvailable,
}: {
  documentId: string
  reviewId: string | null
  fileAvailable: boolean
}) {
  const [open, setOpen] = useState(false)
  const [draftSearch, setDraftSearch] = useState('')
  const [search, setSearch] = useState('')
  const searchId = useId()
  const source = useQuery({
    queryKey: [
      'household',
      'documents',
      'source',
      documentId,
      reviewId,
      search,
    ],
    enabled: open,
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ search })
      if (reviewId) params.set('review_id', reviewId)
      const result = parseEvidenceSource(
        await apiRequest<unknown>(
          `/api/intake/evidence/${encodeURIComponent(documentId)}/source?${params}`,
          { signal },
        ),
      )
      if (reviewId && result.reviewId !== reviewId)
        throw new Error(
          'The evidence does not match this review. Refresh the document.',
        )
      return result
    },
    staleTime: 60_000,
  })
  return (
    <details
      className="mt-3 min-w-0 scroll-mt-64 rounded-lg border p-3 text-sm md:scroll-mt-48"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer font-medium">
        Source evidence & receipt arithmetic
      </summary>
      {open && (
        <div className="mt-3 space-y-3">
          {fileAvailable && (
            <a
              href={`/api/intake/evidence/${encodeURIComponent(documentId)}/file`}
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              Open original file
            </a>
          )}
          <p className="text-xs text-text-muted">
            Extracted text from{' '}
            {reviewId ? 'this exact review' : 'the latest saved review'}.
            Compare it with the original before accepting a correction.
          </p>
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              setSearch(draftSearch.trim())
            }}
          >
            <div className="min-w-0 flex-1">
              <label htmlFor={searchId}>Find in source</label>
              <Input
                id={searchId}
                value={draftSearch}
                maxLength={100}
                onChange={(event) => setDraftSearch(event.target.value)}
              />
            </div>
            <Button type="submit" variant="outline" size="sm">
              Find
            </Button>
            {search && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearch('')
                  setDraftSearch('')
                }}
              >
                Clear search
              </Button>
            )}
          </form>
          {source.isPending && <p role="status">Loading source evidence…</p>}
          {source.isError && (
            <p role="alert">
              Source evidence could not be loaded.{' '}
              <Button
                variant="outline"
                size="sm"
                onClick={() => void source.refetch()}
              >
                Retry source
              </Button>
            </p>
          )}
          {source.data && (
            <>
              {source.data.questions.length > 0 && (
                <div>
                  <p className="font-medium">Questions raised by this review</p>
                  <ul className="list-disc space-y-1 pl-5">
                    {source.data.questions.map((question, index) => (
                      <li key={`${index}-${question}`}>{question}</li>
                    ))}
                  </ul>
                  <a href="#money-clarifications" className="text-xs underline">
                    Open current clarifications to answer
                  </a>
                </div>
              )}
              {source.data.arithmetic.map((row, index) => (
                <div
                  key={`${row.merchant}-${index}`}
                  className="rounded border p-3"
                >
                  <p className="font-medium">
                    {row.merchant} · {row.readableLines} readable lines
                  </p>
                  <dl className="mt-2 grid grid-cols-2 gap-1 text-xs">
                    <dt>Lines after discounts</dt>
                    <dd>{amount(row.lineTotal)}</dd>
                    <dt>Printed subtotal</dt>
                    <dd>{amount(row.subtotal)}</dd>
                    <dt>Printed tax</dt>
                    <dd>{amount(row.tax)}</dd>
                    <dt>Printed total</dt>
                    <dd>{amount(row.total)}</dd>
                  </dl>
                  <p className="mt-2 text-xs">
                    {row.lineDifference === null
                      ? 'Line/subtotal check unavailable.'
                      : Math.abs(row.lineDifference) <= 0.05
                        ? 'Lines match the subtotal within 5¢.'
                        : `Lines differ from the subtotal by ${amount(row.lineDifference)}.`}{' '}
                    {row.totalDifference === null
                      ? 'Subtotal + tax check unavailable.'
                      : Math.abs(row.totalDifference) <= 0.05
                        ? 'Subtotal + tax match the total within 5¢.'
                        : `Subtotal + tax differ from the total by ${amount(row.totalDifference)}. Check fees, discounts, and unreadable lines in the original.`}
                  </p>
                </div>
              ))}
              {source.data.text ? (
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-surface-muted p-3 font-mono text-xs">
                  {source.data.text}
                </pre>
              ) : (
                <p className="text-text-muted">
                  {search
                    ? 'No matching source text.'
                    : 'No extracted source text is saved for this evidence.'}
                </p>
              )}
              {source.data.truncated && (
                <p className="text-xs text-text-muted">
                  Showing the first 6,000 characters. Search for a specific line
                  or open the original file.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </details>
  )
}
