import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { apiRequest } from '@/lib/api/client'
import type {
  HouseholdDocument,
  HouseholdDocumentList,
  HouseholdTransactionDateIssue,
  ImportCenter,
} from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import { DocumentCard } from './DocumentCard'
import { useMoneyQuery } from './useMoneyQuery'

export function ImportCenterSidebar({
  importCenter,
  dateQualityIssues = [],
  focusedReview = false,
}: {
  importCenter?: ImportCenter
  dateQualityIssues?: HouseholdTransactionDateIssue[]
  focusedReview?: boolean
}) {
  const [view, setView] = useMoneyQuery('intakeView', 'pending')
  const [documentId, setDocumentId] = useMoneyQuery('document', '')
  const selected = useQuery({
    queryKey: ['household', 'documents', 'detail', documentId],
    enabled: !!documentId,
    queryFn: () =>
      apiRequest<HouseholdDocument>(
        `/api/intake/evidence/${encodeURIComponent(documentId)}`,
      ),
  })
  const evidence = useInfiniteQuery({
    queryKey: ['household', 'documents', 'queue', view],
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) =>
      apiRequest<HouseholdDocumentList>(
        `/api/intake/evidence?view=${view === 'history' ? 'history' : 'pending'}&limit=8&offset=${pageParam}`,
        { signal },
      ),
    getNextPageParam: (last) =>
      last.offset + last.items.length < last.totalCount
        ? last.offset + last.items.length
        : undefined,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
  const pages = evidence.data?.pages
  const visibleDocuments =
    pages
      ?.flatMap((page) => page.items)
      .filter((item) => item.id !== documentId) ?? []
  const count = pages?.[0]?.pendingCount

  useEffect(() => {
    if (!focusedReview) {
      return
    }
    const target = document.getElementById('date-quality-review')
    if (!target) {
      return
    }
    requestAnimationFrame(() => {
      target.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
    })
  }, [focusedReview, dateQualityIssues.length])

  return (
    <div className="space-y-3">
      {documentId && (
        <section
          className="space-y-3 rounded-lg border border-primary/50 p-3"
          aria-label="Selected evidence"
        >
          <div className="flex justify-between">
            <h3 className="font-medium">Selected evidence</h3>
            <Button variant="ghost" size="sm" onClick={() => setDocumentId('')}>
              Clear selection
            </Button>
          </div>
          {selected.isPending && <p role="status">Loading evidence…</p>}
          {selected.isError && (
            <p role="alert">
              This evidence could not be loaded.{' '}
              <button
                type="button"
                className="underline"
                onClick={() => void selected.refetch()}
              >
                Retry
              </button>
            </p>
          )}
          {selected.data && <DocumentCard document={selected.data} />}
        </section>
      )}
      <div className="flex gap-2" aria-label="Evidence view">
        <Button
          variant={view === 'pending' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setView('pending')}
        >
          Pending decisions{count == null ? '' : ` (${count})`}
        </Button>
        <Button
          variant={view === 'history' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setView('history')}
        >
          History
        </Button>
      </div>
      {view === 'history' && importCenter ? (
        <IntakeSummaryCard importCenter={importCenter} />
      ) : null}
      {dateQualityIssues.length > 0 ? (
        <DateQualityIssuesCard
          issues={dateQualityIssues}
          focusedReview={focusedReview}
        />
      ) : null}
      {evidence.isPending ? (
        <p role="status">Loading pending decisions…</p>
      ) : evidence.isError && !pages ? (
        <p role="alert">
          Evidence could not be loaded.{' '}
          <Button variant="outline" onClick={() => void evidence.refetch()}>
            Retry evidence
          </Button>
        </p>
      ) : visibleDocuments.length === 0 ? (
        <p className="rounded-xl border p-4 text-sm text-text-muted">
          {documentId &&
          pages?.some((page) =>
            page.items.some((item) => item.id === documentId),
          )
            ? 'The matching evidence is shown above.'
            : view === 'history'
              ? 'No money evidence on file yet.'
              : 'No pending document decisions.'}
        </p>
      ) : (
        visibleDocuments.map((document) => (
          <DocumentCard key={document.id} document={document} />
        ))
      )}
      {evidence.hasNextPage && (
        <Button
          variant="outline"
          disabled={evidence.isFetchingNextPage}
          onClick={() => void evidence.fetchNextPage()}
        >
          {evidence.isFetchingNextPage ? 'Loading…' : 'Show more evidence'}
        </Button>
      )}
      {evidence.isError && pages && (
        <p role="alert">
          The evidence list could not be refreshed.{' '}
          <Button variant="outline" onClick={() => void evidence.refetch()}>
            Retry evidence
          </Button>
        </p>
      )}
    </div>
  )
}

function formatFutureDistance(transactionDate: string) {
  const parsedDate = new Date(`${transactionDate}T00:00:00`)
  if (Number.isNaN(parsedDate.getTime())) {
    return null
  }
  const today = new Date()
  const dayDelta = Math.ceil(
    (parsedDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
  )
  if (dayDelta <= 0) {
    return null
  }
  if (dayDelta < 45) {
    return `${dayDelta} day${dayDelta === 1 ? '' : 's'} from now`
  }
  const monthDelta = Math.max(1, Math.round(dayDelta / 30))
  return `${monthDelta} month${monthDelta === 1 ? '' : 's'} from now`
}

function DateQualityIssuesCard({
  issues,
  focusedReview,
}: {
  issues: HouseholdTransactionDateIssue[]
  focusedReview: boolean
}) {
  return (
    <div
      id="date-quality-review"
      className={`rounded-2xl border p-4 ${
        focusedReview
          ? 'border-amber-400/60 bg-amber-400/10 shadow-[0_0_0_1px_rgba(251,191,36,0.18)]'
          : 'border-border/40 bg-surface-muted/20'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text">
            {issues.length} transaction{issues.length === 1 ? '' : 's'}{' '}
            {issues.length === 1 ? 'has a future date' : 'have future dates'}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            Held out of spend, freshness, and budget calculations until the
            evidence date is corrected.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">Needs review</Badge>
          <Button asChild size="sm" variant="outline">
            <a href="#add-evidence-upload">Upload corrected evidence</a>
          </Button>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {issues.slice(0, 5).map((issue) => (
          <div
            key={issue.id}
            className="rounded-2xl border border-border/40 bg-surface/70 p-3"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-text">
                  {issue.merchant}
                </p>
                <p className="mt-1 text-xs text-text-muted">{issue.filename}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold tabular-nums text-text">
                  {formatCurrencyWhole(issue.amount)}
                </p>
                <p className="text-xs text-amber-200">
                  extracted {issue.transactionDate}
                  {formatFutureDistance(issue.transactionDate)
                    ? ` · ${formatFutureDistance(issue.transactionDate)}`
                    : ''}
                </p>
              </div>
            </div>
            {issue.sourceExcerpt ? (
              <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-text-muted/80">
                Evidence: {issue.sourceExcerpt}
              </p>
            ) : null}
            <div className="mt-3">
              <Button asChild size="sm" variant="outline">
                <a href="#add-evidence-upload">Re-upload corrected file</a>
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function IntakeSummaryCard({ importCenter }: { importCenter: ImportCenter }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <p className="text-sm font-semibold text-text">Recent intake</p>
      <p className="mt-1 text-sm text-text-muted">
        Completed and pending evidence, newest first.
      </p>
      <div className="mt-3">
        <div className="rounded-2xl border border-border/40 bg-surface/60 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            Documents
          </p>
          <p className="mt-2 text-2xl font-semibold text-text">
            {importCenter.trackedDocuments}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            {importCenter.parsedDocuments} parsed so far
          </p>
        </div>
      </div>
    </div>
  )
}
