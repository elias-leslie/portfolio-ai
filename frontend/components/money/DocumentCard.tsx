import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { HouseholdDocument } from '@/lib/api/household'
import { formatEnumLabel, formatFileSize } from '@/lib/formatters'
import { useDeleteHouseholdDocument } from '@/lib/hooks/useHousehold'
import { formatDate } from '@/lib/utils'

export function DocumentCard({ document }: { document: HouseholdDocument }) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const deleteDocument = useDeleteHouseholdDocument()
  const metadata =
    document.metadata && typeof document.metadata === 'object'
      ? document.metadata
      : {}
  const applicationSummary =
    metadata.application_summary &&
    typeof metadata.application_summary === 'object' &&
    !Array.isArray(metadata.application_summary)
      ? (metadata.application_summary as Record<string, unknown>)
      : null
  const fileAvailable = metadata.file_available === true
  const showClassifierBadge =
    document.classificationConfidence != null &&
    document.reviewConfidence == null
  const showSourceAvailabilityBadge =
    !fileAvailable &&
    document.reviewStatus !== 'complete' &&
    document.status !== 'parsed'
  const classifierPct =
    document.classificationConfidence != null
      ? Math.round(document.classificationConfidence * 100)
      : null

  return (
    <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text">{document.filename}</p>
          <p className="mt-1 text-sm text-text-muted">
            {formatEnumLabel(document.sourceType, 'Source pending')} ·{' '}
            {formatEnumLabel(document.documentType, 'Type pending')}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant="secondary">
              {formatEnumLabel(document.status, 'staged')}
            </Badge>
            {showClassifierBadge ? (
              <Badge variant="outline">Classifier {classifierPct}%</Badge>
            ) : null}
            {applicationSummary?.status === 'applied' ? (
              <Badge variant="success">Applied</Badge>
            ) : applicationSummary?.status === 'incomplete' ? (
              <Badge variant="outline">Needs follow-up</Badge>
            ) : null}
            {showSourceAvailabilityBadge ? (
              <Badge variant="outline">Source file unavailable</Badge>
            ) : null}
          </div>
          {document.accountLabel ? (
            <p className="mt-1 text-sm text-text-muted">
              {document.accountLabel}
            </p>
          ) : null}
          {document.reviewSummary ? (
            <p className="mt-2 text-sm text-text-muted">
              {document.reviewSummary}
            </p>
          ) : null}
          {applicationSummary ? (
            <p className="mt-2 text-xs text-text-muted">
              {buildApplicationSummary(applicationSummary)}
            </p>
          ) : null}
          <p className="mt-2 text-xs text-text-muted">
            Uploaded <RelativeTime value={document.uploadedAt} />
            {document.parsedAt ? (
              <>
                {' · Parsed '}
                <RelativeTime value={document.parsedAt} />
              </>
            ) : null}
          </p>
          <StatementDates document={document} />
        </div>
        <div className="flex flex-col items-end gap-1 text-right text-xs text-text-muted">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-7 w-7 text-text-muted hover:text-destructive"
            aria-label={`Discard ${document.filename}`}
            onClick={() => setConfirmOpen(true)}
            disabled={deleteDocument.isPending}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          {document.reviewStatus ? (
            <p>
              Jenny: {formatEnumLabel(document.reviewStatus)}
              {document.reviewConfidence != null
                ? ` (${Math.round(document.reviewConfidence * 100)}%)`
                : ''}
            </p>
          ) : null}
          {document.fileSizeBytes > 0 ? (
            <>
              <p>{formatFileSize(document.fileSizeBytes)}</p>
              {document.contentType ? <p>{document.contentType}</p> : null}
            </>
          ) : null}
        </div>
      </div>
      <Dialog
        open={confirmOpen}
        onOpenChange={(open) => {
          if (!deleteDocument.isPending) setConfirmOpen(open)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Discard evidence document</DialogTitle>
            <DialogDescription>
              Remove{' '}
              <span className="font-medium text-text">{document.filename}</span>{' '}
              from intake history. Imported rows tied to this document are
              removed; ledger transactions already written stay in place.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={deleteDocument.isPending}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => {
                deleteDocument.mutate(document.id, {
                  onSuccess: () => setConfirmOpen(false),
                })
              }}
              disabled={deleteDocument.isPending}
              aria-busy={deleteDocument.isPending}
            >
              {deleteDocument.isPending ? 'Discarding...' : 'Discard'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function buildApplicationSummary(summary: Record<string, unknown>): string {
  const parts: string[] = []
  const transactionSummary =
    summary.transactions && typeof summary.transactions === 'object'
      ? (summary.transactions as Record<string, unknown>)
      : null
  const imported =
    summary.imports && typeof summary.imports === 'object'
      ? (summary.imports as Record<string, unknown>)
      : null
  const txCount =
    Number(transactionSummary?.inserted ?? 0) +
    Number(transactionSummary?.updated ?? 0)
  const importCount = Number(imported?.inserted ?? 0)
  const accountCount = Number(summary.evidence_accounts ?? 0)
  const planningCount = Number(summary.planning_items ?? 0)
  const inferredCount = Number(summary.inferred_values ?? 0)

  if (txCount > 0)
    parts.push(`${txCount} transaction${txCount === 1 ? '' : 's'}`)
  if (importCount > 0)
    parts.push(`${importCount} import row${importCount === 1 ? '' : 's'}`)
  if (accountCount > 0)
    parts.push(
      `${accountCount} account snapshot${accountCount === 1 ? '' : 's'}`,
    )
  if (planningCount > 0)
    parts.push(
      `${planningCount} planning item${planningCount === 1 ? '' : 's'}`,
    )
  if (inferredCount > 0)
    parts.push(
      `${inferredCount} inferred value${inferredCount === 1 ? '' : 's'}`,
    )

  if (parts.length === 0) {
    return 'Reviewed, but not enough safe structured output applied yet.'
  }
  return `Applied to ${parts.join(', ')}.`
}

function StatementDates({ document }: { document: HouseholdDocument }) {
  if (document.statementStart && document.statementEnd) {
    return (
      <p className="mt-1 text-xs text-text-muted">
        Statement window {formatDate(document.statementStart, true)} to{' '}
        {formatDate(document.statementEnd, true)}
      </p>
    )
  }
  if (document.statementStart) {
    return (
      <p className="mt-1 text-xs text-text-muted">
        Statement start {formatDate(document.statementStart, true)}
      </p>
    )
  }
  if (document.statementEnd) {
    return (
      <p className="mt-1 text-xs text-text-muted">
        Statement end {formatDate(document.statementEnd, true)}
      </p>
    )
  }
  return null
}
