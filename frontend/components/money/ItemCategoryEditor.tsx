'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { HouseholdPurchaseItem } from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import {
  useCategorizePurchaseItem,
  useSetPurchaseItemOwner,
  useTransactionPurchaseItems,
} from '@/lib/hooks/useHouseholdPurchases'
import { CategoryEditorForm } from './CategoryEditorForm'
import {
  buildCategoryOptions,
  type RecategorizeDraft,
  startRecategorizeDraft,
} from './category-options'

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
  const setItemOwner = useSetPurchaseItemOwner()
  const [draft, setDraft] = useState<RecategorizeDraft | null>(null)
  const [ownerDraft, setOwnerDraft] = useState<{
    itemId: string
    ownerName: string
    applyToProduct: boolean
  } | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)

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

  function startEdit(item: HouseholdPurchaseItem) {
    setDraft(startRecategorizeDraft(item))
    setPickerOpen(false)
  }

  async function saveEdit(item: HouseholdPurchaseItem) {
    if (!draft || !draft.category.trim()) {
      return
    }
    await categorizeItem.mutateAsync({
      itemId: item.id,
      category: draft.category.trim(),
      essentiality: draft.essentiality,
      applyToProduct: draft.applyToMerchant,
    })
    setDraft(null)
    setPickerOpen(false)
  }

  function startOwnerEdit(item: HouseholdPurchaseItem) {
    setOwnerDraft({
      itemId: item.id,
      ownerName: item.ownerName ?? '',
      applyToProduct: false,
    })
  }

  async function saveOwnerEdit() {
    if (!ownerDraft) {
      return
    }
    await setItemOwner.mutateAsync({
      itemId: ownerDraft.itemId,
      ownerName: ownerDraft.ownerName.trim() || null,
      applyToProduct: ownerDraft.applyToProduct,
    })
    setOwnerDraft(null)
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
        const isEditing = draft?.transactionId === item.id
        const isOwnerEditing = ownerDraft?.itemId === item.id
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
                  {item.category} · {formatEnumLabel(item.essentiality)}
                  {' · '}
                  Owner:{' '}
                  <span className="text-text">
                    {item.ownerName ?? 'Unassigned'}
                  </span>
                  {item.categorizationSource === 'manual' ? (
                    <Badge variant="outline" className="ml-2 text-[10px]">
                      Manual
                    </Badge>
                  ) : null}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="font-mono text-sm tabular-nums text-text">
                  {formatCurrency(item.allocatedAmount ?? item.amount, {
                    decimals: 2,
                  })}
                </span>
                {!isEditing ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2 text-xs"
                    aria-label={`Edit category for ${item.description}`}
                    onClick={() => startEdit(item)}
                  >
                    Edit
                  </Button>
                ) : null}
                {!isOwnerEditing ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2 text-xs"
                    aria-label={`Edit owner for ${item.description}`}
                    onClick={() => startOwnerEdit(item)}
                  >
                    Owner
                  </Button>
                ) : null}
              </div>
            </div>
            {isOwnerEditing && ownerDraft ? (
              <div className="mt-2 w-full space-y-3 rounded-xl border border-border/35 bg-surface-muted/15 p-3 lg:w-[420px]">
                <div className="space-y-1.5">
                  <Label htmlFor={`owner-${item.id}`}>Owner</Label>
                  <Input
                    id={`owner-${item.id}`}
                    value={ownerDraft.ownerName}
                    onChange={(event) =>
                      setOwnerDraft((current) =>
                        current
                          ? { ...current, ownerName: event.target.value }
                          : current,
                      )
                    }
                    placeholder="Household, Alex, Jordan..."
                  />
                </div>
                <label className="flex items-start gap-2 text-sm text-text-muted">
                  <Checkbox
                    checked={ownerDraft.applyToProduct}
                    onCheckedChange={(checked) =>
                      setOwnerDraft((current) =>
                        current
                          ? { ...current, applyToProduct: checked === true }
                          : current,
                      )
                    }
                  />
                  <span>Apply to this product going forward.</span>
                </label>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setOwnerDraft(null)}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    disabled={setItemOwner.isPending}
                    onClick={() => void saveOwnerEdit()}
                  >
                    {setItemOwner.isPending ? 'Saving...' : 'Save owner'}
                  </Button>
                </div>
              </div>
            ) : null}
            {isEditing && draft ? (
              <div className="mt-2">
                <CategoryEditorForm
                  transactionId={item.id}
                  draft={draft}
                  setDraft={setDraft}
                  pickerOpen={pickerOpen}
                  onPickerOpenChange={setPickerOpen}
                  categoryOptions={categoryOptions}
                  applyLabel="Apply to this product going forward"
                  pending={categorizeItem.isPending}
                  onSave={() => void saveEdit(item)}
                  onCancel={() => {
                    setDraft(null)
                    setPickerOpen(false)
                  }}
                />
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
