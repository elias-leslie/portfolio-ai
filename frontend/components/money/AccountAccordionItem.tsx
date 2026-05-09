import { Pencil, Trash2 } from 'lucide-react'
import { InfoBadge } from '@/components/shared/InfoBadge'
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import type {
  HouseholdAccountSummary,
  HouseholdDocument,
} from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import { formatRelativeTime } from '@/lib/utils'
import { EvidenceUploadComposer } from './EvidenceUploadComposer'
import {
  accountCoverageDetail,
  accountEvidenceDate,
  accountMetaLine,
  accountSubline,
  freshnessToneClass,
  moneyRoleLabel,
} from './moneyAccountsUtils'

type MoneyAccountsIntent = 'evidence' | 'review' | null

type Props = {
  account: HouseholdAccountSummary
  documentsById: Record<string, HouseholdDocument>
  focusedAccountId: string | undefined
  selectedAccountId: string | null
  intent: MoneyAccountsIntent
  isPendingDelete: boolean
  onEdit: (account: HouseholdAccountSummary) => void
  onDelete: (account: HouseholdAccountSummary) => void
}

export function AccountAccordionItem({
  account,
  documentsById,
  focusedAccountId,
  selectedAccountId,
  intent,
  isPendingDelete,
  onEdit,
  onDelete,
}: Props) {
  const topGap = account.gapFlags[0] ?? null
  const isFocused = account.id === focusedAccountId
  const pricedPositionCount = account.pricedPositionCount ?? 0

  return (
    <AccordionItem
      value={account.id}
      id={`account-${account.id}`}
      className={`px-5 ${
        isFocused ? 'border-primary/50 bg-primary/5 ring-1 ring-primary/30' : ''
      }`}
    >
      <AccordionTrigger className="py-5 hover:text-text">
        <div className="grid flex-1 gap-3 text-left md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_auto] md:items-center">
          <div className="min-w-0">
            <p className="truncate text-base font-semibold text-text">
              {account.label}
            </p>
            <p className="mt-1 truncate text-sm text-text-muted">
              {accountMetaLine(account)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {accountSubline(account)}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <span
              className={`rounded-full border px-2.5 py-1 text-xs ${freshnessToneClass(
                account.balanceFreshnessStatus,
              )}`}
            >
              Balance {account.balanceFreshnessLabel}
            </span>
            {account.moneyRole === 'spend_driver' ? (
              <span
                className={`rounded-full border px-2.5 py-1 text-xs ${freshnessToneClass(
                  account.transactionFreshnessStatus,
                )}`}
              >
                Activity {account.transactionFreshnessLabel}
              </span>
            ) : null}
            {pricedPositionCount > 0 ? (
              <InfoBadge
                label={`Quotes ${account.quoteFreshnessLabel ?? 'Live'}`}
                detail={[
                  `${pricedPositionCount} priced position${pricedPositionCount === 1 ? '' : 's'}`,
                  account.quoteUpdatedAt
                    ? `oldest quote ${formatRelativeTime(account.quoteUpdatedAt)}`
                    : null,
                  account.quoteSource ? `source ${account.quoteSource}` : null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
                variant={
                  account.quoteFreshnessStatus === 'fresh'
                    ? 'success'
                    : account.quoteFreshnessStatus === 'aging'
                      ? 'warning'
                      : account.quoteFreshnessStatus === 'stale'
                        ? 'secondary'
                        : 'outline'
                }
                className="bg-surface/70 text-text-muted"
                interactive={false}
              />
            ) : null}
            <InfoBadge
              label="Coverage"
              detail={accountCoverageDetail(account, topGap)}
              variant="outline"
              className="bg-surface/70 text-text-muted"
              interactive={false}
            />
          </div>

          <div className="text-left md:text-right">
            <p className="text-lg font-semibold tabular-nums text-text">
              {account.currentValue != null
                ? formatCurrencyWhole(account.currentValue)
                : '—'}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {account.moneyRole === 'spend_driver'
                ? 'Spending account'
                : 'Net worth account'}
            </p>
          </div>
        </div>
      </AccordionTrigger>

      <AccordionContent className="pb-5">
        <div className="grid gap-4 xl:grid-cols-[0.92fr_1.08fr]">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-end gap-2">
              {account.trackedAccountId ? (
                <>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onEdit(account)}
                  >
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onDelete(account)}
                    disabled={isPendingDelete}
                    aria-busy={isPendingDelete}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onEdit(account)}
                >
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </Button>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                  Status
                </p>
                <div className="mt-2 space-y-1 text-sm text-text">
                  <p>
                    Balance {account.balanceFreshnessLabel} ·{' '}
                    {accountEvidenceDate(
                      account.lastBalanceAt,
                      account.daysSinceBalance,
                    )}
                  </p>
                  <p>
                    {account.moneyRole === 'spend_driver'
                      ? `Transactions ${account.transactionFreshnessLabel} · ${accountEvidenceDate(
                          account.lastTransactionAt,
                          account.daysSinceTransaction,
                        )}`
                      : 'Transactions not required'}
                  </p>
                  {pricedPositionCount > 0 ? (
                    <p>Quotes {account.quoteFreshnessLabel ?? 'Live'}</p>
                  ) : null}
                  <p className="text-text-muted">
                    {account.lastEvidenceAt
                      ? `Last evidence ${formatRelativeTime(account.lastEvidenceAt)}`
                      : 'No evidence yet'}
                  </p>
                  <p className="text-text-muted">
                    {account.evidenceCount} source
                    {account.evidenceCount === 1 ? '' : 's'}
                  </p>
                </div>
              </div>
              <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                  Identity
                </p>
                <div className="mt-2 space-y-1 text-sm text-text">
                  <p>{moneyRoleLabel(account.moneyRole)}</p>
                  <p className="text-text-muted">
                    {account.accountOrigin === 'tracked'
                      ? 'Account'
                      : account.accountOrigin === 'portfolio'
                        ? 'Investing source only'
                        : account.matchStatus === 'candidate'
                          ? 'Candidate account'
                          : 'Evidence-backed'}
                  </p>
                </div>
              </div>
            </div>

            <div id={`account-evidence-upload-${account.id}`}>
              <EvidenceUploadComposer
                compact
                highlighted={
                  account.id === selectedAccountId && intent === 'evidence'
                }
                title="Add evidence to this account"
                description="Uploads here are bound to this account. Jenny verifies the contents before applying the update."
                accountLabel={account.label}
                householdAccountId={account.householdAccountId}
              />
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                  Supporting documents
                </p>
              </div>
              {account.documentIds.length === 0 ? (
                <p className="mt-3 text-sm text-text-muted">
                  No supporting documents are attached yet.
                </p>
              ) : (
                <div className="mt-3 space-y-2">
                  {account.documentIds.map((documentId) => {
                    const doc = documentsById[documentId]
                    return (
                      <div
                        key={documentId}
                        className="flex items-center justify-between gap-3 rounded-2xl border border-border/30 bg-surface/70 px-3 py-3"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-text">
                            {doc?.filename ?? documentId}
                          </p>
                          <p className="mt-1 text-xs text-text-muted">
                            {doc?.sourceType ?? 'unknown'} ·{' '}
                            {doc?.status ?? 'stored review'}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs text-text-muted">
                          {doc?.uploadedAt
                            ? formatRelativeTime(doc.uploadedAt)
                            : 'Stored review'}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </AccordionContent>
    </AccordionItem>
  )
}
