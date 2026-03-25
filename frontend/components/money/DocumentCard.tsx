import type { HouseholdDocument } from '@/lib/api/household'
import { Badge } from '@/components/ui/badge'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import { formatEnumLabel, formatFileSize } from '@/lib/formatters'

export function DocumentCard({ document }: { document: HouseholdDocument }) {
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
            {document.classificationConfidence != null ? (
              <Badge variant="outline">
                Classifier {Math.round(document.classificationConfidence * 100)}%
              </Badge>
            ) : null}
          </div>
          {document.accountLabel ? (
            <p className="mt-1 text-sm text-text-muted">{document.accountLabel}</p>
          ) : null}
          {document.reviewSummary ? (
            <p className="mt-2 text-sm text-text-muted">{document.reviewSummary}</p>
          ) : null}
          <p className="mt-2 text-xs text-text-muted">
            Uploaded {formatRelativeTime(document.uploadedAt)}
            {document.parsedAt ? ` · Parsed ${formatRelativeTime(document.parsedAt)}` : ''}
          </p>
          <StatementDates document={document} />
        </div>
        <div className="text-right text-xs text-text-muted">
          {document.reviewStatus ? (
            <p className="mt-1">
              Jenny: {formatEnumLabel(document.reviewStatus)}
              {document.reviewConfidence != null
                ? ` (${Math.round(document.reviewConfidence * 100)}%)`
                : ''}
            </p>
          ) : null}
          <p className="mt-1">{formatFileSize(document.fileSizeBytes)}</p>
          {document.contentType ? <p className="mt-1">{document.contentType}</p> : null}
        </div>
      </div>
    </div>
  )
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
