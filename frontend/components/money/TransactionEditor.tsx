'use client'

import { ChevronDown } from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { HouseholdSpendingTransaction } from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import { formatBudgetDate, type RecategorizeDraft } from './budget-helpers'
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
  const categoryListId = `category-options-${transaction.id}`
  const merchantKey = transaction.merchant.trim().toLowerCase()
  const similarMerchantCount =
    merchantAggregates.get(merchantKey)?.transactionCount ?? 1

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
          </p>
        ) : null}
      </div>

      <div className="flex min-w-[280px] flex-col gap-3 lg:items-end">
        <p className="text-right font-mono tabular-nums text-text">
          {formatCurrency(transaction.amount, { decimals: 2 })}
        </p>
        {isEditing && recategorizeDraft ? (
          <div className="w-full space-y-3 rounded-xl border border-border/35 bg-surface-muted/15 p-3 lg:w-[420px]">
            <div className="grid gap-3 sm:grid-cols-[1fr_150px]">
              <div
                className="relative space-y-1.5"
                onBlur={(event) => {
                  const nextFocus = event.relatedTarget
                  if (
                    nextFocus instanceof Node &&
                    event.currentTarget.contains(nextFocus)
                  ) {
                    return
                  }
                  setCategoryPickerOpenFor((current) =>
                    current === transaction.id ? null : current,
                  )
                }}
              >
                <Label htmlFor={`category-${transaction.id}`}>Category</Label>
                <div className="relative">
                  <Input
                    id={`category-${transaction.id}`}
                    value={recategorizeDraft.category}
                    role="combobox"
                    aria-expanded={isCategoryPickerOpen}
                    aria-controls={categoryListId}
                    aria-autocomplete="list"
                    className="pr-10"
                    onFocus={() => setCategoryPickerOpenFor(transaction.id)}
                    onClick={() => setCategoryPickerOpenFor(transaction.id)}
                    onChange={(event) => {
                      setRecategorizeDraft((current) =>
                        current
                          ? { ...current, category: event.target.value }
                          : current,
                      )
                      setCategoryPickerOpenFor(transaction.id)
                    }}
                  />
                  <button
                    type="button"
                    aria-label="Show category options"
                    aria-expanded={isCategoryPickerOpen}
                    aria-controls={categoryListId}
                    className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-text-muted transition-colors hover:text-text"
                    onClick={() =>
                      setCategoryPickerOpenFor((current) =>
                        current === transaction.id ? null : transaction.id,
                      )
                    }
                  >
                    <ChevronDown className="h-4 w-4" />
                  </button>
                </div>
                {isCategoryPickerOpen ? (
                  <div
                    id={categoryListId}
                    role="listbox"
                    aria-label="Existing categories"
                    className="absolute left-0 right-0 top-full z-50 mt-1 max-h-64 overflow-auto rounded-xl border border-border/50 bg-surface p-1 shadow-xl"
                  >
                    {categoryOptions.map((category) => (
                      <button
                        key={category}
                        type="button"
                        role="option"
                        aria-selected={category === recategorizeDraft.category}
                        className={cn(
                          'flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-text transition-colors hover:bg-surface-muted/70',
                          category === recategorizeDraft.category &&
                            'bg-primary/15 text-primary',
                        )}
                        onClick={() => {
                          setRecategorizeDraft((current) =>
                            current ? { ...current, category } : current,
                          )
                          setCategoryPickerOpenFor(null)
                        }}
                      >
                        <span>{category}</span>
                        {category === recategorizeDraft.category ? (
                          <span className="text-xs font-medium">Selected</span>
                        ) : null}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
              <div className="space-y-1.5">
                <Label>Type</Label>
                <Select
                  value={recategorizeDraft.essentiality}
                  onValueChange={(value) =>
                    setRecategorizeDraft((current) =>
                      current ? { ...current, essentiality: value } : current,
                    )
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="essential">Essential</SelectItem>
                    <SelectItem value="mixed">Mixed</SelectItem>
                    <SelectItem value="discretionary">Discretionary</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <label className="flex items-start gap-2 text-sm text-text-muted">
              <Checkbox
                checked={recategorizeDraft.applyToMerchant}
                onCheckedChange={(checked) =>
                  setRecategorizeDraft((current) =>
                    current
                      ? {
                          ...current,
                          applyToMerchant: checked === true,
                        }
                      : current,
                  )
                }
              />
              <span>
                Apply to this merchant going forward
                {similarMerchantCount > 1
                  ? ` and update ${similarMerchantCount} matching purchases`
                  : ''}
                .
              </span>
            </label>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setRecategorizeDraft(null)
                  setCategoryPickerOpenFor(null)
                }}
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => onSaveRecategorize(transaction)}
                disabled={
                  categorizePending || !recategorizeDraft.category.trim()
                }
              >
                {categorizePending ? 'Saving...' : 'Save'}
              </Button>
            </div>
          </div>
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
