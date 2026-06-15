'use client'

import { Badge } from '@/components/ui/badge'
import type { HouseholdPurchaseItem } from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { formatLedgerDate } from './ledger-helpers'
import { PurchaseItemOwnerSelect } from './PurchaseItemOwnerSelect'

interface PurchaseItemsOwnerTableProps {
  items: HouseholdPurchaseItem[]
  isLoading: boolean
  hasData: boolean
  categoryOwnerMap: Map<string, string>
}

export function PurchaseItemsOwnerTable({
  items,
  isLoading,
  hasData,
  categoryOwnerMap,
}: PurchaseItemsOwnerTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
      <div className="max-h-[52vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
        <table className="w-full min-w-[960px] border-separate border-spacing-0 text-sm">
          <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
            <tr>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Item
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Vendor
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Category
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Amount
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Owner
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && !hasData ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-10 text-center text-sm text-text-muted"
                >
                  Loading receipt and invoice items...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-10 text-center text-sm text-text-muted"
                >
                  No receipt or invoice items match this search.
                </td>
              </tr>
            ) : (
              items.map((item) => {
                const inheritedOwnerName =
                  categoryOwnerMap.get(item.category) ?? null
                return (
                  <tr
                    key={item.id}
                    className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                  >
                    <td className="border-b border-border/20 px-3 py-2.5">
                      <div className="font-medium text-text">
                        {item.description}
                      </div>
                      <div className="text-xs text-text-muted">
                        {[
                          item.productName,
                          item.quantity ? `qty ${item.quantity}` : null,
                        ]
                          .filter(Boolean)
                          .join(' · ') || '—'}
                      </div>
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5">
                      <div className="text-text">{item.merchant ?? '—'}</div>
                      <div className="text-xs text-text-muted">
                        {formatLedgerDate(item.purchaseDate)}
                      </div>
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5">
                      <Badge variant="outline">
                        {formatEnumLabel(item.category)}
                      </Badge>
                      <div className="mt-1 text-xs text-text-muted">
                        {formatEnumLabel(item.essentiality)}
                      </div>
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                      {formatCurrency(item.allocatedAmount ?? item.amount, {
                        decimals: 2,
                      })}
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5">
                      <PurchaseItemOwnerSelect
                        itemId={item.id}
                        itemLabel={item.description}
                        ownerName={item.ownerName}
                        ownerSource={item.ownerSource}
                        inheritedOwnerName={inheritedOwnerName}
                      />
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
