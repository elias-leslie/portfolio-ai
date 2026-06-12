import { useEffect, useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type {
  HouseholdDocument,
  HouseholdTransactionDateIssue,
  ImportCenter,
} from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import { DocumentCard } from './DocumentCard'

export function ImportCenterSidebar({
  documents,
  importCenter,
  dateQualityIssues = [],
  focusedReview = false,
}: {
  documents: HouseholdDocument[]
  importCenter?: ImportCenter
  dateQualityIssues?: HouseholdTransactionDateIssue[]
  focusedReview?: boolean
}) {
  const [showAllDocuments, setShowAllDocuments] = useState(false)
  const visibleDocuments = useMemo(
    () => (showAllDocuments ? documents : documents.slice(0, 8)),
    [documents, showAllDocuments],
  )
  const hiddenDocumentCount = Math.max(
    documents.length - visibleDocuments.length,
    0,
  )

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
      {importCenter ? <IntakeSummaryCard importCenter={importCenter} /> : null}
      {dateQualityIssues.length > 0 ? (
        <DateQualityIssuesCard
          issues={dateQualityIssues}
          focusedReview={focusedReview}
        />
      ) : null}
      {documents.length === 0 ? (
        <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-5 text-sm text-text-muted">
          No money evidence on file yet.
        </div>
      ) : (
        <>
          {visibleDocuments.map((document) => (
            <DocumentCard key={document.id} document={document} />
          ))}
          {documents.length > 8 ? (
            <div className="flex justify-center pt-1">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setShowAllDocuments((current) => !current)}
              >
                {showAllDocuments
                  ? 'Show recent only'
                  : `Show ${hiddenDocumentCount} older file${hiddenDocumentCount === 1 ? '' : 's'}`}
              </Button>
            </div>
          ) : null}
        </>
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
        One intake rail. Latest files first. Older evidence stays available
        without taking over the page.
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
