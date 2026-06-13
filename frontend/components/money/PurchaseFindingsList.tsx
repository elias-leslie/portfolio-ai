'use client'

import { Badge } from '@/components/ui/badge'
import type { HouseholdPriceFinding } from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'

interface PurchaseFindingsListProps {
  findings: HouseholdPriceFinding[]
}

export function PurchaseFindingsList({ findings }: PurchaseFindingsListProps) {
  if (findings.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-6">
        <p className="text-sm font-semibold text-text">
          No savings findings yet.
        </p>
        <p className="mt-2 text-sm text-text-muted">
          Run a price check and material savings (at least $3 or 15% on repeat
          buys) will land here — never in your alerts.
        </p>
      </div>
    )
  }

  return (
    <ul className="space-y-2">
      {findings.map((finding) => (
        <li
          key={finding.id}
          className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/40 bg-surface/45 px-4 py-3"
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-text">
              {finding.kind === 'savings_rollup'
                ? (finding.detail ?? 'Combined savings opportunity')
                : (finding.productName ?? 'Product')}
            </p>
            {finding.kind === 'cheaper_elsewhere' && (
              <p className="mt-0.5 text-xs text-text-muted">
                {formatEnumLabel(finding.vendorKey ?? '')} quoted{' '}
                {finding.vendorTitle ?? 'a comparable item'}
                {finding.vendorPackageLabel
                  ? ` (${finding.vendorPackageLabel})`
                  : ''}{' '}
                for {formatCurrency(finding.vendorPrice ?? 0, { decimals: 2 })}{' '}
                vs your{' '}
                {formatCurrency(finding.householdPrice ?? 0, { decimals: 2 })}
                {finding.vendorUrl && (
                  <>
                    {' · '}
                    <a
                      href={finding.vendorUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="underline decoration-border underline-offset-2 hover:text-text"
                    >
                      view item
                    </a>
                  </>
                )}
              </p>
            )}
          </div>
          <Badge variant="success">
            Save {formatCurrency(finding.savingsEstimate ?? 0, { decimals: 2 })}
          </Badge>
        </li>
      ))}
    </ul>
  )
}
