'use client'

import type { Dispatch, SetStateAction } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HouseholdSpendingTransaction } from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { formatBudgetDate } from './budget-helpers'
import { CategoryEditorForm } from './CategoryEditorForm'
import type { RecategorizeDraft } from './category-options'
import type { MerchantAggregate } from './merchant-aggregation'

export interface TransactionEditorProps {
  transaction: HouseholdSpendingTransaction
  recategorizeDraft: RecategorizeDraft | null
  setRecategorizeDraft: Dispatch<SetStateAction<RecategorizeDraft | null>>
  categoryPickerOpenFor: string | null
  setCategoryPickerOpenFor: Dispatch<SetStateAction<string | null>>
  categoryOptions: string[]
  merchantAggregates: Map<string, MerchantAggregate>
  categorizePending: boolean
  onStartRecategorize: (transaction: HouseholdSpendingTransaction) => void
  onSaveRecategorize: (transaction: HouseholdSpendingTransaction) => void
}

export function TransactionEditor({
  transaction,
  recategorizeDraft,
  setRecategorizeDraft,
  categoryPickerOpenFor,
  setCategoryPickerOpenFor,
  categoryOptions,
  merchantAggregates,
  categorizePending,
  onStartRecategorize,
  onSaveRecategorize,
}: TransactionEditorProps) {
  const isEditing = recategorizeDraft?.transactionId === transaction.id
  const isCategoryPickerOpen = categoryPickerOpenFor === transaction.id
  const merchantKey = transaction.merchant.trim().toLowerCase()
  const similarMerchantCount =
    merchantAggregates.get(merchantKey)?.transactionCount ?? 1
  const isItemizedSlice = Boolean(transaction.splitParentId)

  return (
    <div
      key={transaction.id}
      className="grid gap-3 border-b border-border/20 px-4 py-3 last:border-b-0 lg:grid-cols-[1fr_auto]"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium text-text">{transaction.merchant}</p>
          {transaction.needsCategoryReview ||
          transaction.category === 'Unknown' ? (
            <Badge variant="warning">Needs category</Badge>
          ) : null}
          {(transaction.itemCount ?? 0) > 0 ? (
            <Badge
              variant="outline"
              title={
                transaction.itemCategories?.length
                  ? `Split across ${transaction.itemCategories.join(' · ')}`
                  : undefined
              }
            >
              Split · {transaction.itemCount} item
              {transaction.itemCount === 1 ? '' : 's'}
            </Badge>
          ) : null}
          {isItemizedSlice ? (
            <Badge variant="secondary">Itemized portion</Badge>
          ) : null}
        </div>
        <p className="mt-1 text-xs text-text-muted">
          {formatBudgetDate(transaction.date)} ·{' '}
          {transaction.accountLabel ?? 'No account'} · {transaction.description}
        </p>
        {!isEditing ? (
          <p className="mt-2 text-xs text-text-muted">
            {transaction.category} · {formatEnumLabel(transaction.essentiality)}
            {transaction.categoryConfidence != null
              ? ` · ${(transaction.categoryConfidence * 100).toFixed(0)}% confidence`
              : ''}
            {transaction.ownerName ? ` · Owner: ${transaction.ownerName}` : ''}
          </p>
        ) : null}
      </div>

      <div className="flex min-w-[280px] flex-col gap-3 lg:items-end">
        <p className="text-right font-mono tabular-nums text-text">
          {formatCurrency(transaction.amount, { decimals: 2 })}
        </p>
        {isItemizedSlice ? (
          <p className="max-w-[260px] text-right text-xs text-text-muted">
            Category and owner come from linked purchase items. Edit them from
            the Ledger item drawer.
          </p>
        ) : isEditing && recategorizeDraft ? (
          <CategoryEditorForm
            transactionId={transaction.id}
            draft={recategorizeDraft}
            setDraft={setRecategorizeDraft}
            pickerOpen={isCategoryPickerOpen}
            onPickerOpenChange={(open) =>
              setCategoryPickerOpenFor((current) =>
                open
                  ? transaction.id
                  : current === transaction.id
                    ? null
                    : current,
              )
            }
            categoryOptions={categoryOptions}
            similarMerchantCount={similarMerchantCount}
            pending={categorizePending}
            onSave={() => onSaveRecategorize(transaction)}
            onCancel={() => {
              setRecategorizeDraft(null)
              setCategoryPickerOpenFor(null)
            }}
          />
        ) : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => onStartRecategorize(transaction)}
          >
            Categorize
          </Button>
        )}
      </div>
    </div>
  )
}
