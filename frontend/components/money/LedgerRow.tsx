import { Fragment, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import {
  type InlineComboboxCommitOptions,
  InlineComboboxField,
} from './InlineComboboxField'
import { ItemCategoryEditor } from './ItemCategoryEditor'
import {
  entryDate,
  formatLedgerDate,
  type HouseholdLedgerEntry,
  ledgerAmountLabel,
  ledgerRowKey,
  utcDateKey,
} from './ledger-helpers'

interface LedgerRowProps {
  entry: HouseholdLedgerEntry
  auditOpen: boolean
  onToggleAudit: (rowKey: string | null) => void
  categoryOptions: string[]
  categorizePending: boolean
  onCommitCategory?: (
    category: string,
    options?: InlineComboboxCommitOptions,
  ) => void
}

/** Enum label with the "api" word kept as the acronym ("api_sync" → "API sync"). */
function formatSourceEnumLabel(value: string) {
  return formatEnumLabel(value).replace(/\bApi\b/g, 'API')
}

export function LedgerRow({
  entry,
  auditOpen,
  onToggleAudit,
  categoryOptions,
  categorizePending,
  onCommitCategory,
}: LedgerRowProps) {
  const [applyToMerchant, setApplyToMerchant] = useState<boolean | null>(null)
  const hasMerchantRule =
    entry.transactionRuleId != null ||
    entry.categorizationSource === 'merchant_rule'
  const merchantRuleChecked = applyToMerchant ?? hasMerchantRule
  const effectiveDate = entryDate(entry)
  const effectiveDateKey = utcDateKey(effectiveDate)
  const isFuture =
    effectiveDateKey != null &&
    effectiveDateKey > new Date().toISOString().slice(0, 10)
  const rowKey = ledgerRowKey(entry)
  const evidenceLabel = entry.sourceDocumentId
    ? 'Evidence linked'
    : 'No evidence'
  const evidenceDetail =
    [
      entry.sourceType ? formatSourceEnumLabel(entry.sourceType) : null,
      entry.documentType ? formatSourceEnumLabel(entry.documentType) : null,
    ]
      .filter(Boolean)
      .join(' · ') || 'Stored row'
  const isCredit = entry.direction === 'credit'
  const showInlineItems = entry.itemCount > 0
  return (
    <Fragment key={rowKey}>
      <tr
        data-ledger-row="entry"
        className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
      >
        <td className="border-b border-border/20 px-3 py-2.5 align-top">
          <div className="font-medium text-text">
            {formatLedgerDate(effectiveDate)}
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            <Badge
              variant={entry.kind === 'transaction' ? 'default' : 'outline'}
              className="w-fit"
            >
              {entry.kind === 'transaction'
                ? formatEnumLabel(entry.flowType ?? 'transaction')
                : formatEnumLabel(entry.datasetType ?? 'import_row')}
            </Badge>
            {isFuture ? <Badge variant="destructive">Future</Badge> : null}
            {entry.pending ? <Badge variant="warning">Pending</Badge> : null}
          </div>
        </td>
        <td className="border-b border-border/20 px-3 py-2.5 align-top">
          <div className="font-medium text-text">
            {entry.accountLabel ?? '—'}
          </div>
          <div className="text-xs text-text-muted">
            {entry.currency ?? 'USD'}
          </div>
        </td>
        <td className="border-b border-border/20 px-3 py-2.5 align-top">
          <div className="font-medium text-text">
            {entry.merchant || entry.description}
          </div>
          {entry.description && entry.description !== entry.merchant ? (
            <div className="text-xs text-text-muted">{entry.description}</div>
          ) : null}
        </td>
        <td className="border-b border-border/20 px-3 py-2.5 align-top">
          {onCommitCategory ? (
            <InlineComboboxField
              id={`ledger-category-${rowKey}`}
              label={`Category for ${entry.merchant || entry.description}`}
              value={entry.category || ''}
              options={categoryOptions}
              disabled={categorizePending}
              ruleLabel="Merchant rule"
              ruleChecked={merchantRuleChecked}
              onRuleCheckedChange={setApplyToMerchant}
              className="w-[170px]"
              onCommit={onCommitCategory}
            />
          ) : (
            <span className="font-medium text-text">
              {entry.category ? formatEnumLabel(entry.category) : '—'}
            </span>
          )}
          <div className="text-xs text-text-muted">
            {entry.essentiality ? formatEnumLabel(entry.essentiality) : '—'}
          </div>
          {entry.itemCategories.length > 1 ? (
            <div className="mt-1 text-xs text-text-muted">
              Split: {entry.itemCategories.join(' · ')}
            </div>
          ) : null}
        </td>
        <td className="border-b border-border/20 px-3 py-2.5 text-right align-top">
          <div
            className={cn(
              'font-mono font-medium tabular-nums',
              isCredit ? 'text-gain' : 'text-text',
            )}
          >
            {ledgerAmountLabel(entry)}
          </div>
          <div className="mt-1 text-xs text-text-muted">
            {isCredit ? 'Credit' : 'Debit'}
          </div>
        </td>
        <td className="border-b border-border/20 px-3 py-2.5 align-top">
          <div className="flex flex-wrap gap-1">
            <Badge
              variant={entry.includedInSpend ? 'default' : 'outline'}
              className="w-fit"
            >
              {entry.includedInSpend ? 'Counted' : 'Excluded'}
            </Badge>
          </div>
          <div className="mt-1 text-xs text-text-muted">
            {entry.exclusionReason
              ? formatEnumLabel(entry.exclusionReason)
              : 'Included in canonical spend'}
          </div>
        </td>
        <td className="border-b border-border/20 px-3 py-2.5 align-top">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={entry.sourceDocumentId ? 'outline' : 'secondary'}>
              {evidenceLabel}
            </Badge>
            {entry.itemCount > 0 ? (
              <Badge variant="secondary">
                {entry.itemCount} item{entry.itemCount === 1 ? '' : 's'} below
              </Badge>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              aria-expanded={auditOpen}
              aria-controls={`ledger-audit-${rowKey}`}
              onClick={() => onToggleAudit(auditOpen ? null : rowKey)}
            >
              Audit
            </Button>
          </div>
          <div className="mt-1 text-xs text-text-muted">{evidenceDetail}</div>
        </td>
      </tr>
      {showInlineItems ? (
        <tr
          id={`ledger-items-${rowKey}`}
          data-ledger-row="items"
          className="bg-surface-muted/10"
        >
          <td colSpan={7} className="border-b border-border/20 px-3 py-3">
            <div className="rounded-xl border border-border/35 bg-surface/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-text">
                    Purchase items
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Line items behind this charge. Category edits move budget
                    and spending splits; owner dropdowns save item-level
                    overrides.
                  </p>
                </div>
              </div>
              <div className="mt-4">
                <ItemCategoryEditor
                  transactionId={entry.id}
                  transactionAmount={entry.amount}
                />
              </div>
            </div>
          </td>
        </tr>
      ) : null}
      {auditOpen ? (
        <tr
          id={`ledger-audit-${rowKey}`}
          data-ledger-row="audit"
          className="bg-surface-muted/10"
        >
          <td colSpan={7} className="border-b border-border/20 px-3 py-3">
            <div className="rounded-xl border border-border/35 bg-surface/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-text">
                    Audit detail
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Provenance and debug identifiers for this ledger row.
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onToggleAudit(null)}
                >
                  Hide audit
                </Button>
              </div>
              <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Source file
                  </dt>
                  <dd className="mt-1 break-all text-text">
                    {entry.sourceDocumentFilename ?? 'Unknown source'}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Source type
                  </dt>
                  <dd className="mt-1 text-text">{evidenceDetail}</dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Document id
                  </dt>
                  <dd className="mt-1 break-all text-text">
                    {entry.sourceDocumentId ?? '—'}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Row hash
                  </dt>
                  <dd className="mt-1 break-all font-mono text-text">
                    {entry.rowHash}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    External row id
                  </dt>
                  <dd className="mt-1 break-all text-text">
                    {entry.externalRowId ?? '—'}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Balance after
                  </dt>
                  <dd className="mt-1 font-mono tabular-nums text-text">
                    {formatCurrency(entry.balanceAfter, {
                      decimals: 2,
                      nullDisplay: '—',
                    })}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Uploaded
                  </dt>
                  <dd className="mt-1 text-text">
                    {formatLedgerDate(entry.uploadedAt)}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Exclusion reason
                  </dt>
                  <dd className="mt-1 text-text">
                    {entry.exclusionReason
                      ? formatEnumLabel(entry.exclusionReason)
                      : 'Included in canonical spend'}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Settlement
                  </dt>
                  <dd className="mt-1 text-text">
                    {entry.pending ? 'Pending' : 'Posted'}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Categorized by
                  </dt>
                  <dd className="mt-1 text-text">
                    {entry.categorizationSource
                      ? formatEnumLabel(entry.categorizationSource)
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Original category
                  </dt>
                  <dd className="mt-1 text-text">
                    {entry.originalCategory
                      ? formatEnumLabel(entry.originalCategory)
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                    Recategorized
                  </dt>
                  <dd className="mt-1 text-text">
                    {entry.categoryUpdatedBy
                      ? `${entry.categoryUpdatedBy}${
                          entry.categoryUpdatedAt
                            ? ` · ${formatLedgerDate(entry.categoryUpdatedAt)}`
                            : ''
                        }`
                      : '—'}
                  </dd>
                </div>
              </dl>
            </div>
          </td>
        </tr>
      ) : null}
    </Fragment>
  )
}
