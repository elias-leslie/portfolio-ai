'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HouseholdProductSummary } from '@/lib/api/household'
import { formatCurrency } from '@/lib/formatters'
import { formatLedgerDate } from './ledger-helpers'
import { PriceHistorySparkline } from './PriceHistorySparkline'
import { PurchaseItemOwnerSelect } from './PurchaseItemOwnerSelect'

interface ProductCatalogTableProps {
  products: HouseholdProductSummary[]
  isLoading: boolean
  hasData: boolean
  onOpenProduct: (productId: string) => void
}

export function ProductCatalogTable({
  products,
  isLoading,
  hasData,
  onOpenProduct,
}: ProductCatalogTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
      <div className="max-h-[60vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
        <table className="w-full min-w-[1080px] border-separate border-spacing-0 text-sm">
          <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
            <tr>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Product
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Purchases
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Latest price
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Price trend
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Last seen
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Owner
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && !hasData ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-10 text-center text-sm text-text-muted"
                >
                  Loading products...
                </td>
              </tr>
            ) : products.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-10 text-center text-sm text-text-muted"
                >
                  No products match. Receipt and order-history evidence builds
                  the catalog.
                </td>
              </tr>
            ) : (
              products.map((product) => (
                <tr
                  key={product.id}
                  className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                >
                  <td className="border-b border-border/20 px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-text">
                        {product.canonicalName}
                      </span>
                      {product.needsReviewCount > 0 ? (
                        <Badge variant="warning">Review</Badge>
                      ) : null}
                    </div>
                    <div className="text-xs text-text-muted">
                      {[product.brand, product.packageDisplayLabel]
                        .filter(Boolean)
                        .join(' · ') || '—'}
                    </div>
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                    {product.purchaseCount}
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                    {formatCurrency(product.latestPrice, {
                      decimals: 2,
                      nullDisplay: '—',
                    })}
                    <div className="text-xs text-text-muted">
                      {product.latestUnitPrice != null
                        ? `${formatCurrency(product.latestUnitPrice, { decimals: 2 })}/unit`
                        : (product.latestMerchant ?? '')}
                    </div>
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5">
                    <PriceHistorySparkline points={product.pricePoints} />
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5 text-text">
                    {formatLedgerDate(product.lastObservedDate)}
                    <div className="text-xs text-text-muted">
                      {product.latestMerchant ?? '—'}
                    </div>
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5">
                    {product.ownerItemId ? (
                      <PurchaseItemOwnerSelect
                        itemId={product.ownerItemId}
                        itemLabel={product.canonicalName}
                        ownerName={product.ownerName}
                        ownerSource={product.ownerSource}
                        forceProductRule
                      />
                    ) : (
                      <span className="text-xs text-text-muted">—</span>
                    )}
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5 text-right">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      onClick={() => onOpenProduct(product.id)}
                    >
                      Details
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
