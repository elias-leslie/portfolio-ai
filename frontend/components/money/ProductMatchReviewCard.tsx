'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { HouseholdPurchaseItem } from '@/lib/api/household'
import { formatCurrency, formatPercent } from '@/lib/formatters'
import {
  useAssignPurchaseItemProduct,
  useHouseholdProducts,
} from '@/lib/hooks/useHouseholdPurchases'
import { formatLedgerDate } from './ledger-helpers'
import { PurchaseItemOwnerSelect } from './PurchaseItemOwnerSelect'
import { useCategoryOwnerMap } from './useCategoryOwnerMap'

interface ProductMatchReviewCardProps {
  items: HouseholdPurchaseItem[]
  totalCount: number
}

/** Confirm / reassign / detach low-confidence product matches. */
export function ProductMatchReviewCard({
  items,
  totalCount,
}: ProductMatchReviewCardProps) {
  const assignProduct = useAssignPurchaseItemProduct()
  const categoryOwnerMap = useCategoryOwnerMap()
  const [reassigningItemId, setReassigningItemId] = useState<string | null>(
    null,
  )
  const [reassignSearch, setReassignSearch] = useState('')
  const reassignQuery = reassignSearch.trim()
  const { data: candidates } = useHouseholdProducts(
    reassignQuery ? { search: reassignQuery, limit: 5 } : undefined,
  )

  async function act(
    itemId: string,
    action: 'confirm' | 'reassign' | 'detach',
    productId?: string,
  ) {
    await assignProduct.mutateAsync({ itemId, action, productId })
    if (reassigningItemId === itemId) {
      setReassigningItemId(null)
      setReassignSearch('')
    }
  }

  if (items.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        No product matches waiting on review. Low-confidence matches from new
        receipts land here.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {totalCount > items.length ? (
        <p className="text-xs text-text-muted">
          Showing {items.length} of {totalCount} items needing review.
        </p>
      ) : null}
      {items.map((item) => {
        const inheritedOwnerName = categoryOwnerMap.get(item.category) ?? null
        return (
          <div
            key={item.id}
            className="rounded-2xl border border-border/40 bg-surface-muted/10 p-3"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-medium text-text">{item.description}</p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {formatLedgerDate(item.purchaseDate)} ·{' '}
                  {item.merchant ?? 'Unknown vendor'} ·{' '}
                  {formatCurrency(item.amount, { decimals: 2 })}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  Matched to{' '}
                  <span className="text-text">
                    {item.productName ?? 'no product'}
                  </span>
                  {item.productMatchConfidence != null ? (
                    <Badge variant="warning" className="ml-2">
                      {formatPercent(item.productMatchConfidence * 100, {
                        decimals: 0,
                      })}{' '}
                      match
                    </Badge>
                  ) : null}
                </p>
                <div className="mt-2">
                  <PurchaseItemOwnerSelect
                    itemId={item.id}
                    itemLabel={item.description}
                    ownerName={item.ownerName}
                    ownerSource={item.ownerSource}
                    inheritedOwnerName={inheritedOwnerName}
                  />
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={assignProduct.isPending || item.productId == null}
                  onClick={() => void act(item.id, 'confirm')}
                >
                  Confirm
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={assignProduct.isPending}
                  onClick={() => {
                    setReassigningItemId((current) =>
                      current === item.id ? null : item.id,
                    )
                    setReassignSearch('')
                  }}
                >
                  Reassign
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={assignProduct.isPending}
                  onClick={() => void act(item.id, 'detach')}
                >
                  Detach
                </Button>
              </div>
            </div>
            {reassigningItemId === item.id ? (
              <div className="mt-3 rounded-xl border border-border/30 bg-surface/60 p-3">
                <Input
                  value={reassignSearch}
                  onChange={(event) => setReassignSearch(event.target.value)}
                  placeholder="Search the correct product"
                  aria-label={`Search product for ${item.description}`}
                />
                {reassignQuery
                  ? (candidates?.products ?? [])
                      .filter((candidate) => candidate.id !== item.productId)
                      .map((candidate) => (
                        <div
                          key={candidate.id}
                          className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-border/30 px-3 py-2 text-sm"
                        >
                          <span className="min-w-0 truncate text-text">
                            {candidate.canonicalName}
                            <span className="ml-2 text-xs text-text-muted">
                              {candidate.purchaseCount} purchases
                            </span>
                          </span>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={assignProduct.isPending}
                            onClick={() =>
                              void act(item.id, 'reassign', candidate.id)
                            }
                          >
                            Use this product
                          </Button>
                        </div>
                      ))
                  : null}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
