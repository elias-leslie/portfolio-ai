import { Badge } from '@/components/ui/badge'
import type { HouseholdDocument } from '@/lib/api/household'
import { formatEnumLabel, formatFileSize } from '@/lib/formatters'
import { formatDate, formatRelativeTime } from '@/lib/utils'

export function DocumentCard({ document }: { document: HouseholdDocument }) {
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
                Classifier {Math.round(document.classificationConfidence * 100)}
                %
              </Badge>
            ) : null}
            {applicationSummary?.status === 'applied' ? (
              <Badge variant="success">Applied</Badge>
            ) : applicationSummary?.status === 'incomplete' ? (
              <Badge variant="outline">Needs completion</Badge>
            ) : null}
            {!fileAvailable ? (
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
            Uploaded {formatRelativeTime(document.uploadedAt)}
            {document.parsedAt
              ? ` · Parsed ${formatRelativeTime(document.parsedAt)}`
              : ''}
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
          {document.contentType ? (
            <p className="mt-1">{document.contentType}</p>
          ) : null}
        </div>
      </div>
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
    return 'Jenny reviewed this file, but it still needs enough usable evidence to apply it safely.'
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
