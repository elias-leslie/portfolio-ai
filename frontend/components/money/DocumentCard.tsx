import { Check, RotateCw, Trash2, X } from 'lucide-react'
import type { ReactNode } from 'react'
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
import type {
  HouseholdDocument,
  HouseholdDocumentReviewProposalPreview,
} from '@/lib/api/household'
import { formatEnumLabel, formatFileSize } from '@/lib/formatters'
import {
  useDecideHouseholdDocumentReview,
  useDeleteHouseholdDocument,
  useReReviewHouseholdDocument,
} from '@/lib/hooks/useHousehold'
import { formatDate } from '@/lib/utils'

export function DocumentCard({ document }: { document: HouseholdDocument }) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const deleteDocument = useDeleteHouseholdDocument()
  const reReviewDocument = useReReviewHouseholdDocument()
  const decideReview = useDecideHouseholdDocumentReview()
  const metadata =
    document.metadata && typeof document.metadata === 'object'
      ? document.metadata
      : {}
  const applicationSummaryValue =
    metadata.applicationSummary ?? metadata.application_summary
  const applicationSummary =
    applicationSummaryValue &&
    typeof applicationSummaryValue === 'object' &&
    !Array.isArray(applicationSummaryValue)
      ? (applicationSummaryValue as Record<string, unknown>)
      : null
  const reviewProposalValue =
    metadata.reviewProposal ?? metadata.review_proposal
  const reviewProposal =
    reviewProposalValue &&
    typeof reviewProposalValue === 'object' &&
    !Array.isArray(reviewProposalValue)
      ? (reviewProposalValue as Record<string, unknown>)
      : null
  const rawProposalStatus =
    typeof reviewProposal?.status === 'string' ? reviewProposal.status : null
  const schemaVersionValue =
    reviewProposal?.schemaVersion ?? reviewProposal?.schema_version
  const proposalSchemaVersion = Number(schemaVersionValue ?? 0)
  const proposalStatus =
    rawProposalStatus === 'pending' && proposalSchemaVersion !== 2
      ? 'stale'
      : rawProposalStatus
  const reviewIdValue = reviewProposal?.reviewId ?? reviewProposal?.review_id
  const proposalReviewId =
    typeof reviewIdValue === 'string' && reviewIdValue.length > 0
      ? reviewIdValue
      : null
  const proposalHashValue =
    reviewProposal?.proposalHash ?? reviewProposal?.proposal_hash
  const proposalHash =
    typeof proposalHashValue === 'string' &&
    /^[0-9a-f]{64}$/.test(proposalHashValue)
      ? proposalHashValue
      : null
  const proposalPreview = parseProposalPreview(reviewProposal?.preview)
  const proposedChangesValue =
    reviewProposal?.proposedChanges ?? reviewProposal?.proposed_changes
  const proposedChanges = Array.isArray(proposedChangesValue)
    ? proposedChangesValue.filter(
        (item): item is Record<string, unknown> =>
          Boolean(item) && typeof item === 'object' && !Array.isArray(item),
      )
    : []
  const canDecideProposal =
    proposalSchemaVersion === 2 &&
    proposalReviewId != null &&
    proposalHash != null &&
    proposalPreview != null
  const canApproveProposal = canDecideProposal && proposedChanges.length > 0
  const fileAvailable =
    metadata.fileAvailable === true || metadata.file_available === true
  const showClassifierBadge =
    document.classificationConfidence != null &&
    document.reviewConfidence == null
  const showSourceAvailabilityBadge =
    !fileAvailable &&
    document.reviewStatus !== 'complete' &&
    document.status !== 'parsed'
  const showReReviewButton =
    fileAvailable &&
    ((document.status === 'staged' &&
      (document.reviewStatus == null || document.reviewStatus === 'failed')) ||
      proposalStatus === 'rejected' ||
      proposalStatus === 'failed' ||
      proposalStatus === 'stale')
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
            ) : applicationSummary?.status === 'needs_review' &&
              proposalStatus !== 'rejected' &&
              proposalStatus !== 'failed' ? (
              <Badge variant="warning">Approval needed</Badge>
            ) : null}
            {proposalStatus === 'rejected' ? (
              <Badge variant="outline">Rejected</Badge>
            ) : proposalStatus === 'applying' ? (
              <Badge variant="outline">Applying approval</Badge>
            ) : proposalStatus === 'failed' ? (
              <Badge variant="destructive">Approval failed</Badge>
            ) : proposalStatus === 'stale' ? (
              <Badge variant="warning">Re-review required</Badge>
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
          {proposalStatus === 'pending' ||
          proposalStatus === 'applying' ||
          proposalStatus === 'failed' ||
          proposalStatus === 'stale' ? (
            <div
              role="region"
              aria-label={`Review proposal for ${document.filename}`}
              className="mt-3 rounded-xl border border-amber-400/40 bg-amber-400/10 p-3"
            >
              <p className="text-sm font-semibold text-text">
                {proposalStatus === 'failed'
                  ? 'Approval interrupted'
                  : proposalStatus === 'applying'
                    ? 'Approval in progress'
                    : proposalStatus === 'stale'
                      ? 'Fresh review required'
                      : 'Review before applying'}
              </p>
              <p className="mt-1 text-xs text-text-muted">
                {proposalStatus === 'failed'
                  ? 'No second decision is needed. Retry resumes from the last durable phase.'
                  : proposalStatus === 'applying'
                    ? 'If the prior process stopped, resume approval; only one executor can continue.'
                    : proposalStatus === 'stale'
                      ? 'This older proposal did not include an exact cryptographic preview and cannot be approved.'
                      : typeof reviewProposal?.blocker === 'string'
                        ? reviewProposal.blocker
                        : 'Jenny held this review instead of changing your money data.'}
              </p>
              {proposedChanges.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {proposedChanges.map((change) => (
                    <Badge
                      key={String(change.kind ?? change.label)}
                      variant="outline"
                    >
                      {String(change.label ?? 'Proposed change')} ·{' '}
                      {Number(change.count ?? 0)}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-xs text-text-muted">
                  No structured money changes were identified. Reject it or
                  re-run review with clearer evidence.
                </p>
              )}
              {proposalPreview ? (
                <ProposalPreviewDetails preview={proposalPreview} />
              ) : proposalStatus !== 'stale' ? (
                <p className="mt-2 text-xs text-destructive">
                  The exact proposal preview is unavailable. Re-run review
                  before making a decision.
                </p>
              ) : null}
              {proposalStatus !== 'stale' ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    onClick={() =>
                      proposalReviewId &&
                      proposalHash &&
                      proposalPreview &&
                      decideReview.mutate({
                        documentId: document.id,
                        reviewId: proposalReviewId,
                        proposalHash,
                        proposalPreview,
                        decision: 'approve',
                      })
                    }
                    disabled={decideReview.isPending || !canApproveProposal}
                    aria-busy={decideReview.isPending}
                  >
                    <Check className="mr-1 h-3.5 w-3.5" />
                    {proposalStatus === 'pending'
                      ? 'Approve changes'
                      : 'Resume approval'}
                  </Button>
                  {proposalStatus === 'pending' ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        proposalReviewId &&
                        proposalHash &&
                        proposalPreview &&
                        decideReview.mutate({
                          documentId: document.id,
                          reviewId: proposalReviewId,
                          proposalHash,
                          proposalPreview,
                          decision: 'reject',
                        })
                      }
                      disabled={decideReview.isPending || !canDecideProposal}
                    >
                      <X className="mr-1 h-3.5 w-3.5" />
                      Reject
                    </Button>
                  ) : null}
                </div>
              ) : null}
              {proposalStatus !== 'stale' && !canDecideProposal ? (
                <p className="mt-2 text-xs text-destructive">
                  This proposal is stale. Re-run review before making a
                  decision.
                </p>
              ) : null}
            </div>
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
          <div className="flex items-center gap-1">
            {showReReviewButton ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7 px-2 text-xs"
                aria-label={`Re-run Jenny review on ${document.filename}`}
                onClick={() => reReviewDocument.mutate(document.id)}
                disabled={reReviewDocument.isPending}
                aria-busy={reReviewDocument.isPending}
              >
                <RotateCw className="mr-1 h-3 w-3" />
                {reReviewDocument.isPending ? 'Re-running…' : 'Re-run review'}
              </Button>
            ) : null}
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
          </div>
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

function recordList(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> =>
          Boolean(item) && typeof item === 'object' && !Array.isArray(item),
      )
    : []
}

function nullableText(value: unknown): string | null {
  return typeof value === 'string' || typeof value === 'number'
    ? String(value)
    : null
}

function parseProposalPreview(
  value: unknown,
): HouseholdDocumentReviewProposalPreview | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const preview = value as Record<string, unknown>
  return {
    accounts: recordList(preview.accounts).map((account) => ({
      label: nullableText(account.label) ?? 'Account snapshot',
      accountSuffix: nullableText(
        account.accountSuffix ?? account.account_suffix,
      ),
      balance: nullableText(account.balance),
      holdingsValue: nullableText(
        account.holdingsValue ?? account.holdings_value,
      ),
      cashBalance: nullableText(account.cashBalance ?? account.cash_balance),
      currency: nullableText(account.currency),
      asOfDate: nullableText(account.asOfDate ?? account.as_of_date),
    })),
    transactions: recordList(preview.transactions).map((transaction) => ({
      accountLabel: nullableText(
        transaction.accountLabel ?? transaction.account_label,
      ),
      transactionDate: nullableText(
        transaction.transactionDate ?? transaction.transaction_date,
      ),
      merchant: nullableText(transaction.merchant),
      amount: nullableText(transaction.amount),
      currency: nullableText(transaction.currency),
    })),
    holdings: recordList(preview.holdings).map((holding) => ({
      accountLabel: nullableText(holding.accountLabel ?? holding.account_label),
      symbol: nullableText(holding.symbol),
      shares: nullableText(holding.shares),
      value: nullableText(holding.value),
    })),
    planning: recordList(preview.planning).map((item) => ({
      field: nullableText(item.field) ?? 'Planning field',
      value: item.value,
    })),
    inferences: recordList(preview.inferences).map((item) => ({
      field: nullableText(item.field) ?? 'Inferred field',
      value: item.value,
    })),
  }
}

function formatPreviewAmount(amount: string | null, currency = 'USD'): string {
  if (amount == null) return 'Amount unavailable'
  const number = Number(amount)
  if (!Number.isFinite(number)) return amount
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
    }).format(number)
  } catch {
    return `${amount} ${currency}`
  }
}

function formatFieldValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (value == null) return 'Not provided'
  return JSON.stringify(value)
}

function ProposalPreviewDetails({
  preview,
}: {
  preview: HouseholdDocumentReviewProposalPreview
}) {
  const hasValues =
    preview.accounts.length > 0 ||
    preview.transactions.length > 0 ||
    preview.holdings.length > 0 ||
    preview.planning.length > 0 ||
    preview.inferences.length > 0
  if (!hasValues) return null

  return (
    <div
      className="mt-3 space-y-3 rounded-lg border border-border/60 bg-surface/60 p-3"
      aria-label="Exact proposed values"
    >
      <p className="text-xs font-semibold text-text">Exact proposed values</p>
      {preview.accounts.length > 0 ? (
        <PreviewGroup label="Accounts">
          {preview.accounts.map((account, index) => (
            <li key={`${account.label}-${index}`}>
              <span className="font-medium text-text">{account.label}</span>
              {' · Balance '}
              {formatPreviewAmount(account.balance, account.currency ?? 'USD')}
              {account.holdingsValue != null
                ? ` · Holdings ${formatPreviewAmount(account.holdingsValue, account.currency ?? 'USD')}`
                : ''}
              {account.cashBalance != null
                ? ` · Cash ${formatPreviewAmount(account.cashBalance, account.currency ?? 'USD')}`
                : ''}
              {account.asOfDate ? ` · As of ${account.asOfDate}` : ''}
            </li>
          ))}
        </PreviewGroup>
      ) : null}
      {preview.transactions.length > 0 ? (
        <PreviewGroup label="Transactions">
          {preview.transactions.map((transaction, index) => (
            <li
              key={`${transaction.transactionDate}-${transaction.merchant}-${index}`}
            >
              <span className="font-medium text-text">
                {transaction.transactionDate ?? 'Date unavailable'} ·{' '}
                {transaction.merchant ?? 'Merchant unavailable'}
              </span>
              {' · '}
              {formatPreviewAmount(
                transaction.amount,
                transaction.currency ?? 'USD',
              )}
              {transaction.accountLabel ? ` · ${transaction.accountLabel}` : ''}
            </li>
          ))}
        </PreviewGroup>
      ) : null}
      {preview.holdings.length > 0 ? (
        <PreviewGroup label="Holdings">
          {preview.holdings.map((holding, index) => (
            <li key={`${holding.symbol}-${index}`}>
              <span className="font-medium text-text">
                {holding.symbol ?? 'Symbol unavailable'}
              </span>
              {holding.shares != null ? ` · ${holding.shares} shares` : ''}
              {holding.value != null
                ? ` · ${formatPreviewAmount(holding.value)}`
                : ''}
              {holding.accountLabel ? ` · ${holding.accountLabel}` : ''}
            </li>
          ))}
        </PreviewGroup>
      ) : null}
      {preview.planning.length > 0 ? (
        <PreviewGroup label="Planning">
          {preview.planning.map((item, index) => (
            <li key={`${item.field}-${index}`}>
              <span className="font-medium text-text">{item.field}</span>
              {' · '}
              {formatFieldValue(item.value)}
            </li>
          ))}
        </PreviewGroup>
      ) : null}
      {preview.inferences.length > 0 ? (
        <PreviewGroup label="Inferences">
          {preview.inferences.map((item, index) => (
            <li key={`${item.field}-${index}`}>
              <span className="font-medium text-text">{item.field}</span>
              {' · '}
              {formatFieldValue(item.value)}
            </li>
          ))}
        </PreviewGroup>
      ) : null}
    </div>
  )
}

function PreviewGroup({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
        {label}
      </p>
      <ul className="mt-1 space-y-1 text-xs text-text-muted">{children}</ul>
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
  const accountCount = Number(
    summary.evidenceAccounts ?? summary.evidence_accounts ?? 0,
  )
  const planningCount = Number(
    summary.planningItems ?? summary.planning_items ?? 0,
  )
  const inferredCount = Number(
    summary.inferredValues ?? summary.inferred_values ?? 0,
  )

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
