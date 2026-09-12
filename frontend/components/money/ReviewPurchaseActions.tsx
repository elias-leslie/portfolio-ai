'use client'

import Link from 'next/link'
import { useHouseholdBuyGuide } from '@/lib/hooks/useHouseholdPurchases'

/** Current offers are a next-purchase decision, separate from the selected month's result. */
export function ReviewPurchaseActions() {
  const { data, error, isPending, refetch } = useHouseholdBuyGuide()
  return (
    <section
      className="rounded-xl border border-border p-4"
      aria-label="Next purchase decisions"
    >
      <h2 className="text-sm font-semibold">Next purchases · current offers</h2>
      {isPending ? (
        <p className="mt-2 text-sm text-text-muted">
          Checking confirmed price evidence…
        </p>
      ) : error ? (
        <p className="mt-2 text-sm">
          Purchase opportunities could not be checked.{' '}
          <button
            type="button"
            className="underline"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </p>
      ) : !data?.items.length ? (
        <p className="mt-2 text-sm text-text-muted">
          No reliable opportunity found.{' '}
          <Link className="underline" href="/money?tab=purchases">
            Review the staple price evidence
          </Link>
          .
        </p>
      ) : (
        <ul className="mt-3 space-y-3">
          {data.items.slice(0, 3).map((item) => (
            <li key={item.productId} className="text-sm">
              <Link
                className="font-medium underline"
                href={`/money?tab=purchases&product=${encodeURIComponent(item.productId)}`}
              >
                {item.productName}
              </Link>
              <p>
                {item.bestMerchant}: ${item.bestTotalPrice.toFixed(2)} for{' '}
                {item.bestPackageLabel} · ${item.bestUnitCost.toFixed(3)}/
                {item.unitLabel}.
              </p>
              <p className="text-xs text-text-muted">
                {item.estimatedMonthlySavings != null
                  ? `About $${item.estimatedMonthlySavings.toFixed(2)}/month if this price and the observed restocking pace continue. `
                  : ''}
                Offer checked {item.bestObservedDate}
                {item.bestValidUntil &&
                  `, valid through ${item.bestValidUntil}`}
                ; confirm conditions before buying.{' '}
                {item.findingKind === 'bulk_trap_risk'
                  ? 'The larger package may exceed six months of your usual purchases.'
                  : ''}
              </p>
              {item.bestConditions && (
                <p className="text-xs text-text-muted">{item.bestConditions}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
