'use client'

import { ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import type { HouseholdNoveltyCluster } from '@/lib/api/household'
import { formatCurrency, formatCurrencyWhole } from '@/lib/formatters'

export interface NewThisMonthCardProps {
  clusters: HouseholdNoveltyCluster[] | undefined
  monthLabel: string
}

/**
 * Merchants the ledger has never seen, grouped into the outings they were.
 *
 * The grouping is the feature. July 2026 has 34 first-time merchants; as a list
 * that is 34 mystery lines and reads like fraud, and as two date clusters it is
 * two trips. Clusters are built from dates only — these rows carry no location,
 * so nothing here names a place.
 *
 * This answers half of D2's fourth sentence. The other half needs owner
 * attribution, which is still 91% "Family" and cannot say who bought what.
 */
export function NewThisMonthCard({
  clusters,
  monthLabel,
}: NewThisMonthCardProps) {
  const [expanded, setExpanded] = useState<string | null>(null)

  if (!clusters || clusters.length === 0) {
    return null
  }

  const total = clusters.reduce((sum, cluster) => sum + cluster.total, 0)
  const merchantCount = clusters.reduce(
    (sum, cluster) => sum + cluster.merchantCount,
    0,
  )

  return (
    <SectionCard
      variant="surface"
      title="New this month"
      description={`${merchantCount} merchant${merchantCount === 1 ? '' : 's'} with no history before ${monthLabel}, ${formatCurrencyWhole(total)} in total.`}
    >
      <ul className="space-y-2">
        {clusters.map((cluster) => {
          const isOpen = expanded === cluster.key
          return (
            <li
              key={cluster.key}
              className="rounded-xl border border-border/25 bg-surface-muted/10"
            >
              <button
                type="button"
                className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
                onClick={() =>
                  setExpanded((current) =>
                    current === cluster.key ? null : cluster.key,
                  )
                }
                aria-expanded={isOpen}
              >
                <span className="flex items-start gap-2">
                  {cluster.isCluster ? (
                    isOpen ? (
                      <ChevronDown className="mt-0.5 h-4 w-4 text-text-muted" />
                    ) : (
                      <ChevronRight className="mt-0.5 h-4 w-4 text-text-muted" />
                    )
                  ) : (
                    <span className="mt-0.5 h-4 w-4" />
                  )}
                  <span>
                    <span className="block text-sm font-medium text-text">
                      {cluster.label}
                    </span>
                    <span className="mt-0.5 block text-xs text-text-muted">
                      {cluster.detail}
                    </span>
                  </span>
                </span>
                <span className="shrink-0 font-mono text-sm tabular-nums text-text">
                  {formatCurrencyWhole(cluster.total)}
                </span>
              </button>
              {isOpen && cluster.isCluster ? (
                <ul className="border-t border-border/20 px-4 py-2">
                  {cluster.merchants.map((merchant) => (
                    <li
                      key={merchant.merchant}
                      className="flex items-baseline justify-between gap-3 py-1 text-xs"
                    >
                      <span className="text-text">{merchant.merchant}</span>
                      <span className="flex items-baseline gap-3 text-text-muted">
                        <span>{merchant.category}</span>
                        <span className="font-mono tabular-nums text-text">
                          {formatCurrency(merchant.amount, { decimals: 2 })}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          )
        })}
      </ul>
    </SectionCard>
  )
}
