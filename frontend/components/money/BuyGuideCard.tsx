'use client'

import { AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type {
  HouseholdBuyGuideItem,
  HouseholdProductPricePoint,
} from '@/lib/api/household'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import {
  useHouseholdBuyGuide,
  useTriggerPriceCheck,
} from '@/lib/hooks/useHouseholdPurchases'
import { PriceHistorySparkline } from './PriceHistorySparkline'

function unitCurrency(value: number | null | undefined) {
  const decimals = value != null && Math.abs(value) < 1 ? 3 : 2
  return formatCurrency(value, { decimals })
}

function sourceLabel(item: HouseholdBuyGuideItem) {
  const date = new Date(item.bestObservedDate)
  const dateLabel = Number.isNaN(date.getTime())
    ? item.bestObservedDate
    : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return `${formatEnumLabel(item.bestSource)} · ${dateLabel}`
}

function findingVariant(
  kind: string,
): 'default' | 'secondary' | 'success' | 'destructive' | 'warning' {
  if (kind === 'bulk_trap_risk') return 'warning'
  if (kind === 'buy_bigger_same_store' || kind === 'buy_bigger_elsewhere') {
    return 'success'
  }
  return 'secondary'
}

function confidenceLabel(value: number) {
  if (value >= 0.8) return 'High'
  if (value >= 0.6) return 'Medium'
  return 'Low'
}

function trendPricePoints(
  item: HouseholdBuyGuideItem,
): HouseholdProductPricePoint[] {
  return item.trendPoints.map((point) => ({
    observedDate: point.observedDate,
    merchant: point.merchant,
    totalPrice: point.totalPrice,
    unitPrice: point.unitCost,
    source: point.source,
  }))
}

interface BuyGuideCardProps {
  onOpenProduct: (productId: string) => void
}

export function BuyGuideCard({ onOpenProduct }: BuyGuideCardProps) {
  const { data, isLoading, error, refetch, isFetching } = useHouseholdBuyGuide()
  const triggerPriceCheck = useTriggerPriceCheck()
  const rows = data?.items ?? []

  if (error) {
    return (
      <div className="rounded-2xl border border-border/40 bg-surface/45 p-4">
        <p className="text-sm font-semibold text-text">
          Buy Guide failed to load.
        </p>
        <p className="mt-1 text-sm text-text-muted">
          Retry to refresh unit-cost recommendations.
        </p>
        <Button
          type="button"
          size="sm"
          className="mt-3"
          onClick={() => void refetch()}
          disabled={isFetching}
        >
          Retry
        </Button>
      </div>
    )
  }

  if (isLoading) {
    return <p className="text-sm text-text-muted">Loading Buy Guide…</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-border/40 bg-surface/45 p-4">
        <div>
          <p className="text-sm font-semibold text-text">Unit-cost scan</p>
          <p className="mt-1 text-sm text-text-muted">
            {rows.length > 0
              ? `${data?.totalCandidates ?? rows.length} material size/vendor opportunities found from ${data?.unitCoverageCount ?? 0} products with package-unit data.`
              : `${data?.unitCoverageCount ?? 0} products have package-unit data. Run price research to add fresh vendor quotes for recurring buys.`}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => triggerPriceCheck.mutate()}
          disabled={triggerPriceCheck.isPending}
        >
          {triggerPriceCheck.isPending ? 'Starting…' : 'Research prices'}
        </Button>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-6">
          <p className="text-sm font-semibold text-text">
            No buy-size gaps yet.
          </p>
          <p className="mt-2 text-sm text-text-muted">
            The guide only shows material savings after it has actual unit costs
            and a cheaper larger-size or vendor quote. Receipts and order
            history improve this automatically.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="max-h-[40vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
            <table className="w-full min-w-[1180px] border-separate border-spacing-0 text-sm">
              <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
                <tr className="text-left text-xs uppercase tracking-[0.14em] text-text-muted/80">
                  <th className="border-b border-border/40 px-3 py-2">Item</th>
                  <th className="border-b border-border/40 px-3 py-2">
                    Current buy
                  </th>
                  <th className="border-b border-border/40 px-3 py-2">
                    Better unit cost
                  </th>
                  <th className="border-b border-border/40 px-3 py-2">
                    Unit trend
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right">
                    Unit delta
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right">
                    Savings
                  </th>
                  <th className="border-b border-border/40 px-3 py-2">
                    Confidence
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.productId}
                    className="align-top transition-colors hover:bg-surface-muted/20"
                  >
                    <td className="border-b border-border/20 px-3 py-3">
                      <button
                        type="button"
                        className="max-w-[280px] truncate text-left font-medium text-text underline-offset-2 hover:underline"
                        onClick={() => onOpenProduct(row.productId)}
                        title={row.productName}
                      >
                        {row.productName}
                      </button>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        <Badge variant={findingVariant(row.findingKind)}>
                          {formatEnumLabel(row.findingKind)}
                        </Badge>
                        <span className="text-xs text-text-muted">
                          {row.purchaseCount} buys
                        </span>
                      </div>
                    </td>
                    <td className="border-b border-border/20 px-3 py-3 text-text">
                      <p>{row.currentMerchant ?? 'Unknown vendor'}</p>
                      <p className="text-xs text-text-muted">
                        {row.currentPackageLabel ?? 'package'} ·{' '}
                        {unitCurrency(row.currentUnitCost)}/{row.unitLabel}
                      </p>
                    </td>
                    <td className="border-b border-border/20 px-3 py-3 text-text">
                      <p>{row.bestMerchant ?? 'Unknown vendor'}</p>
                      <p className="text-xs text-text-muted">
                        {row.bestPackageLabel ?? row.bestTitle ?? 'package'} ·{' '}
                        {unitCurrency(row.bestUnitCost)}/{row.unitLabel}
                      </p>
                      <p className="mt-1 text-[11px] text-text-muted">
                        {sourceLabel(row)}
                        {row.bestUrl ? (
                          <>
                            {' · '}
                            <a
                              href={row.bestUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="underline decoration-border underline-offset-2 hover:text-text"
                            >
                              view
                            </a>
                          </>
                        ) : null}
                      </p>
                    </td>
                    <td className="border-b border-border/20 px-3 py-3">
                      <PriceHistorySparkline
                        points={trendPricePoints(row)}
                        width={116}
                        height={34}
                      />
                      <p className="mt-1 text-xs text-text-muted">
                        {row.trendPoints.length} obs · unit cost
                      </p>
                    </td>
                    <td className="border-b border-border/20 px-3 py-3 text-right font-mono tabular-nums text-text">
                      -{formatPercent(row.savingsPct, { decimals: 0 })}
                      <div className="text-xs text-text-muted">
                        {unitCurrency(row.savingsPerUnit)}/{row.unitLabel}
                      </div>
                    </td>
                    <td className="border-b border-border/20 px-3 py-3 text-right font-mono tabular-nums text-text">
                      {formatCurrency(row.estimatedMonthlySavings, {
                        decimals: 2,
                        nullDisplay: '—',
                      })}
                      <div className="text-xs text-text-muted">
                        per month est.
                      </div>
                      {row.monthsToUse != null && row.monthsToUse > 6 ? (
                        <div className="mt-1 inline-flex items-center gap-1 text-[11px] text-warning-strong">
                          <AlertTriangle className="h-3 w-3" />{' '}
                          {row.monthsToUse} mo use
                        </div>
                      ) : row.monthsToUse != null ? (
                        <div className="text-xs text-text-muted">
                          {row.monthsToUse} mo use
                        </div>
                      ) : null}
                    </td>
                    <td className="border-b border-border/20 px-3 py-3">
                      <Badge
                        variant={
                          row.confidence >= 0.8 ? 'success' : 'secondary'
                        }
                      >
                        {confidenceLabel(row.confidence)}
                      </Badge>
                      <p className="mt-1 max-w-[260px] text-xs text-text-muted">
                        {row.recommendation}
                      </p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
