'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import type { HouseholdSpendingTransaction } from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { formatBudgetDate } from './budget-helpers'
import {
  type InlineComboboxCommitOptions,
  InlineComboboxField,
} from './InlineComboboxField'

export interface TransactionEditorProps {
  transaction: HouseholdSpendingTransaction
  categoryOptions: string[]
  categorizePending: boolean
  onCommitCategory: (
    transaction: HouseholdSpendingTransaction,
    category: string,
    options?: InlineComboboxCommitOptions,
  ) => void
}

export function TransactionEditor({
  transaction,
  categoryOptions,
  categorizePending,
  onCommitCategory,
}: TransactionEditorProps) {
  const isItemizedSlice = Boolean(transaction.splitParentId)
  const [applyToMerchant, setApplyToMerchant] = useState<boolean | null>(null)
  const hasMerchantRule =
    transaction.transactionRuleId != null ||
    transaction.categorizationSource === 'merchant_rule'
  const merchantRuleChecked = applyToMerchant ?? hasMerchantRule

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
        <p className="mt-2 text-xs text-text-muted">
          {formatEnumLabel(transaction.essentiality)}
          {transaction.categoryConfidence != null
            ? ` · ${(transaction.categoryConfidence * 100).toFixed(0)}% confidence`
            : ''}
          {transaction.ownerName ? ` · Owner: ${transaction.ownerName}` : ''}
        </p>
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
        ) : (
          <InlineComboboxField
            id={`budget-transaction-category-${transaction.id}`}
            label={`Category for ${transaction.merchant}`}
            value={transaction.category}
            options={categoryOptions}
            disabled={categorizePending}
            ruleLabel="Merchant rule"
            ruleChecked={merchantRuleChecked}
            onRuleCheckedChange={setApplyToMerchant}
            className="w-[220px]"
            onCommit={(category, options) =>
              onCommitCategory(transaction, category, options)
            }
          />
        )}
      </div>
    </div>
  )
}
