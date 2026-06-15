'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import type { HouseholdPurchaseItem } from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import {
  useCategorizePurchaseItem,
  useTransactionPurchaseItems,
} from '@/lib/hooks/useHouseholdPurchases'
import { buildCategoryOptions } from './category-options'
import {
  type InlineComboboxCommitOptions,
  InlineComboboxField,
} from './InlineComboboxField'
import { PurchaseItemOwnerSelect } from './PurchaseItemOwnerSelect'
import { useCategoryOwnerMap } from './useCategoryOwnerMap'

interface ItemCategoryEditorProps {
  transactionId: string
  /** Transaction charge amount, for the allocation reconciliation line. */
  transactionAmount?: number | null
}

/**
 * Expanded ledger-row view of an itemized charge: every purchase item with
 * its allocated share and an inline per-item category editor. Saving with
 * "apply to product" upserts a product rule (mirrors merchant rules).
 */
export function ItemCategoryEditor({
  transactionId,
  transactionAmount,
}: ItemCategoryEditorProps) {
  const { data: items, isLoading } = useTransactionPurchaseItems(transactionId)
  const categorizeItem = useCategorizePurchaseItem()
  const categoryOwnerMap = useCategoryOwnerMap()
  const [productRuleItems, setProductRuleItems] = useState<
    Record<string, boolean>
  >({})

  if (isLoading) {
    return <p className="text-sm text-text-muted">Loading items...</p>
  }
  if (!items || items.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        No purchase items linked to this charge.
      </p>
    )
  }

  const allocatedTotal = items.reduce(
    (sum, item) => sum + (item.allocatedAmount ?? 0),
    0,
  )
  const reconciles =
    transactionAmount != null &&
    Math.abs(allocatedTotal - Math.abs(transactionAmount)) < 0.005
  const categoryOptions = buildCategoryOptions(
    items.map((item) => item.category),
  )
  async function saveCategory(
    item: HouseholdPurchaseItem,
    category: string,
    options?: InlineComboboxCommitOptions,
  ) {
    const trimmed = category.trim()
    if (!trimmed) {
      return
    }
    await categorizeItem.mutateAsync({
      itemId: item.id,
      category: trimmed,
      essentiality: item.essentiality || 'mixed',
      applyToProduct: options?.applyRule === true,
    })
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-text-muted">
        {items.length} item{items.length === 1 ? '' : 's'} · allocated{' '}
        <span className="font-mono tabular-nums">
          {formatCurrency(allocatedTotal, { decimals: 2 })}
        </span>
        {transactionAmount != null
          ? reconciles
            ? ' · matches the charge exactly'
            : ' · pending allocation against this charge'
          : ''}
      </p>
      {items.map((item) => {
        const inheritedOwnerName = categoryOwnerMap.get(item.category) ?? null
        return (
          <div
            key={item.id}
            className="rounded-xl border border-border/30 bg-surface/60 px-3 py-2"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-text">
                  {item.description}
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {item.quantity != null && item.quantity !== 1
                    ? `qty ${item.quantity} · `
                    : ''}
                  {item.productName && item.productName !== item.description
                    ? `${item.productName} · `
                    : ''}
                  {formatEnumLabel(item.essentiality)}
                  {' · '}
                  Owner:{' '}
                  <span className="text-text">
                    {item.ownerName ?? inheritedOwnerName ?? 'Unassigned'}
                  </span>
                  {!item.ownerName && inheritedOwnerName ? (
                    <Badge variant="secondary" className="ml-2 text-[10px]">
                      Inherited
                    </Badge>
                  ) : null}
                  {item.categorizationSource === 'manual' ? (
                    <Badge variant="outline" className="ml-2 text-[10px]">
                      Manual
                    </Badge>
                  ) : null}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <InlineComboboxField
                  id={`purchase-item-category-${item.id}`}
                  label={`Category for ${item.description}`}
                  value={item.category}
                  options={categoryOptions}
                  disabled={categorizeItem.isPending}
                  ruleLabel="Product rule"
                  ruleChecked={productRuleItems[item.id] === true}
                  onRuleCheckedChange={(checked) =>
                    setProductRuleItems((current) => ({
                      ...current,
                      [item.id]: checked,
                    }))
                  }
                  className="w-[180px]"
                  onCommit={(category, options) =>
                    void saveCategory(item, category, options)
                  }
                />
                <span className="font-mono text-sm tabular-nums text-text">
                  {formatCurrency(item.allocatedAmount ?? item.amount, {
                    decimals: 2,
                  })}
                </span>
                <PurchaseItemOwnerSelect
                  itemId={item.id}
                  itemLabel={item.description}
                  ownerName={item.ownerName}
                  ownerSource={item.ownerSource}
                  inheritedOwnerName={inheritedOwnerName}
                />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
