'use client'

import { formatCurrency, formatPercent } from '@/lib/formatters'
import { usePurchaseItemLinkage } from '@/lib/hooks/useHouseholdPurchases'
import { formatLedgerDate } from './ledger-helpers'

/**
 * How much of the item layer is tied to money, over a denominator that means
 * something. Every item that is not linked carries the reason it is not, so a
 * limit of what the household has connected never reads as a matching failure.
 */
export function ItemLinkageCard() {
  const { data, isLoading, error } = usePurchaseItemLinkage()

  if (isLoading) {
    return <p className="text-sm text-text-muted">Reading the item layer…</p>
  }
  if (error || !data) {
    return (
      <p className="text-sm text-text-muted">
        Could not read how items tie to charges.
      </p>
    )
  }

  const { addressableItems, linkedItems, addressableLinkedShare } = data
  const unreachable = data.totalItems - addressableItems

  return (
    <div className="space-y-4">
      <div>
        <p className="text-2xl font-semibold text-text">
          {linkedItems.toLocaleString()} of {addressableItems.toLocaleString()}{' '}
          {addressableLinkedShare === null
            ? null
            : `(${formatPercent(addressableLinkedShare * 100)})`}
        </p>
        <p className="text-sm text-text-muted">
          items whose charge could be in the ledger are tied to one.{' '}
          {unreachable > 0 ? (
            <>
              A further {unreachable.toLocaleString()} were bought outside what
              the household has connected
              {data.feedStartsOn
                ? ` — the oldest charge we hold is from ${formatLedgerDate(data.feedStartsOn)}`
                : ''}
              , and are listed below rather than counted as misses.
            </>
          ) : null}
        </p>
      </div>

      <ul className="space-y-2">
        {data.buckets.map((bucket) => (
          <li
            key={bucket.state}
            className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rounded-lg border border-border/30 px-3 py-2"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-text">{bucket.label}</p>
              <p className="text-xs text-text-muted">{bucket.detail}</p>
            </div>
            <p className="whitespace-nowrap text-sm text-text-muted">
              {bucket.itemCount.toLocaleString()} items ·{' '}
              {formatCurrency(bucket.amount)}
            </p>
          </li>
        ))}
      </ul>

      {data.unknownCards.length > 0 ? (
        <div className="space-y-1">
          <p className="text-sm font-medium text-text">
            Cards no account claims
          </p>
          <p className="text-xs text-text-muted">
            Naming one of these ties every item bought on it to an account. A
            card that was reissued is declared as a prior number, not a new
            account.
          </p>
          <ul className="space-y-1 pt-1">
            {data.unknownCards.map((card) => (
              <li
                key={card.mask}
                className="flex flex-wrap items-baseline justify-between gap-x-4 text-sm"
              >
                <span className="text-text">···{card.mask}</span>
                <span className="text-text-muted">
                  {card.itemCount.toLocaleString()} items ·{' '}
                  {formatCurrency(card.amount)}
                  {card.firstSeen && card.lastSeen
                    ? ` · ${formatLedgerDate(card.firstSeen)} – ${formatLedgerDate(card.lastSeen)}`
                    : ''}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
