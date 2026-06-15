'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import {
  useHouseholdProductDetail,
  useHouseholdProducts,
  useMergeHouseholdProducts,
} from '@/lib/hooks/useHouseholdPurchases'
import { formatLedgerDate } from './ledger-helpers'
import { PriceHistorySparkline } from './PriceHistorySparkline'
import { PurchaseItemOwnerSelect } from './PurchaseItemOwnerSelect'
import { useCategoryOwnerMap } from './useCategoryOwnerMap'

interface ProductDetailSheetProps {
  productId: string | null
  onClose: () => void
}

/** Product drill-down: identity, full price history, recent purchases, merge. */
export function ProductDetailSheet({
  productId,
  onClose,
}: ProductDetailSheetProps) {
  const { data: detail, isLoading } = useHouseholdProductDetail(productId)
  const [mergeSearch, setMergeSearch] = useState('')
  const mergeProducts = useMergeHouseholdProducts()
  const categoryOwnerMap = useCategoryOwnerMap()
  const mergeQuery = mergeSearch.trim()
  const { data: mergeCandidates } = useHouseholdProducts(
    mergeQuery ? { search: mergeQuery, scope: 'all', limit: 5 } : undefined,
  )

  function close() {
    setMergeSearch('')
    onClose()
  }

  async function mergeInto(targetProductId: string) {
    if (!productId) {
      return
    }
    await mergeProducts.mutateAsync({
      sourceProductId: productId,
      targetProductId,
    })
    close()
  }

  return (
    <Dialog
      open={productId != null}
      onOpenChange={(open) => {
        if (!open) {
          close()
        }
      }}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {detail?.product.canonicalName ?? 'Product detail'}
          </DialogTitle>
          <DialogDescription>
            {detail
              ? [detail.product.brand, detail.product.packageDisplayLabel]
                  .filter(Boolean)
                  .join(' · ') ||
                'Purchase-price history from receipts and order evidence.'
              : 'Purchase-price history from receipts and order evidence.'}
          </DialogDescription>
        </DialogHeader>

        {isLoading || !detail ? (
          <p className="py-6 text-sm text-text-muted">Loading product...</p>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-4">
              <PriceHistorySparkline
                points={detail.product.pricePoints}
                width={220}
                height={48}
              />
              <div className="text-sm">
                <p className="font-mono tabular-nums text-text">
                  {formatCurrency(detail.product.latestPrice, {
                    decimals: 2,
                    nullDisplay: '—',
                  })}{' '}
                  <span className="text-xs text-text-muted">latest</span>
                </p>
                <p className="text-xs text-text-muted">
                  {detail.product.purchaseCount} purchase
                  {detail.product.purchaseCount === 1 ? '' : 's'} ·{' '}
                  {detail.observations.length} price point
                  {detail.observations.length === 1 ? '' : 's'}
                </p>
              </div>
              <div className="flex flex-wrap gap-1">
                {detail.identifiers.map((identifier) => (
                  <Badge
                    key={`${identifier.kind}-${identifier.value}`}
                    variant="outline"
                    className="max-w-[260px] truncate text-[10px]"
                    title={`${identifier.kind}: ${identifier.value}`}
                  >
                    {identifier.kind}
                  </Badge>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Price history
              </p>
              <div className="mt-2 max-h-[28vh] overflow-auto rounded-xl border border-border/40">
                <table className="w-full border-separate border-spacing-0 text-sm">
                  <thead className="sticky top-0 bg-bg/95 backdrop-blur">
                    <tr className="text-left text-xs uppercase tracking-[0.14em] text-text-muted/80">
                      <th className="border-b border-border/40 px-3 py-2">
                        Date
                      </th>
                      <th className="border-b border-border/40 px-3 py-2">
                        Vendor
                      </th>
                      <th className="border-b border-border/40 px-3 py-2 text-right">
                        Price
                      </th>
                      <th className="border-b border-border/40 px-3 py-2 text-right">
                        Qty
                      </th>
                      <th className="border-b border-border/40 px-3 py-2 text-right">
                        Unit
                      </th>
                      <th className="border-b border-border/40 px-3 py-2">
                        Source
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...detail.observations].reverse().map((observation) => (
                      <tr
                        key={`${observation.observedDate}-${observation.merchant}-${observation.totalPrice}`}
                      >
                        <td className="border-b border-border/20 px-3 py-1.5 text-text">
                          {formatLedgerDate(observation.observedDate)}
                        </td>
                        <td className="border-b border-border/20 px-3 py-1.5 text-text">
                          {observation.merchant ?? '—'}
                        </td>
                        <td className="border-b border-border/20 px-3 py-1.5 text-right font-mono tabular-nums text-text">
                          {formatCurrency(observation.totalPrice, {
                            decimals: 2,
                          })}
                        </td>
                        <td className="border-b border-border/20 px-3 py-1.5 text-right font-mono tabular-nums text-text">
                          {observation.quantity ?? '—'}
                        </td>
                        <td className="border-b border-border/20 px-3 py-1.5 text-right font-mono tabular-nums text-text">
                          {formatCurrency(observation.unitPrice, {
                            decimals: 2,
                            nullDisplay: '—',
                          })}
                        </td>
                        <td className="border-b border-border/20 px-3 py-1.5 text-xs text-text-muted">
                          {formatEnumLabel(observation.source)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {detail.recentItems.length > 0 ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                  Recent purchases
                </p>
                <div className="mt-2 space-y-1">
                  {detail.recentItems.slice(0, 8).map((item) => {
                    const inheritedOwnerName =
                      categoryOwnerMap.get(item.category) ?? null
                    return (
                      <div
                        key={item.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/30 bg-surface-muted/10 px-3 py-2 text-xs"
                      >
                        <span className="min-w-0 truncate text-text">
                          {item.description}
                        </span>
                        <span className="shrink-0 text-text-muted">
                          {formatLedgerDate(item.purchaseDate)} ·{' '}
                          {item.category} ·{' '}
                          <span className="font-mono tabular-nums text-text">
                            {formatCurrency(item.amount, { decimals: 2 })}
                          </span>
                        </span>
                        <PurchaseItemOwnerSelect
                          itemId={item.id}
                          itemLabel={item.description}
                          ownerName={item.ownerName}
                          ownerSource={item.ownerSource}
                          inheritedOwnerName={inheritedOwnerName}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : null}

            <div className="rounded-xl border border-dashed border-border/40 p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Merge duplicate
              </p>
              <p className="mt-1 text-xs text-text-muted">
                Fold this product into another one. Its purchases, price
                history, and rules move to the target.
              </p>
              <Input
                value={mergeSearch}
                onChange={(event) => setMergeSearch(event.target.value)}
                placeholder="Search for the product to keep"
                aria-label="Search merge target product"
                className="mt-2"
              />
              {mergeQuery
                ? (mergeCandidates?.products ?? [])
                    .filter((candidate) => candidate.id !== productId)
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
                          disabled={mergeProducts.isPending}
                          onClick={() => void mergeInto(candidate.id)}
                        >
                          Merge into this
                        </Button>
                      </div>
                    ))
                : null}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
