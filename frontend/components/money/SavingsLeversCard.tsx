import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import {
  priceInsightBadgeLabel,
  priceInsightBadgeVariant,
  signedCurrency,
} from './overview-helpers'
import type { useDecisionBoard } from './useDecisionBoard'

type DecisionBoardData = ReturnType<typeof useDecisionBoard>

export function SavingsLeversCard({
  priceInsights,
  merchantHighlights,
}: Pick<DecisionBoardData, 'priceInsights' | 'merchantHighlights'>) {
  return (
    <SectionCard
      variant="surface"
      title="Savings Levers"
      description="Repeated-item price moves and merchants worth optimizing first."
    >
      <div className="space-y-3">
        {priceInsights.length === 0 && merchantHighlights.length === 0 ? (
          <p className="text-sm text-text-muted">
            No live savings levers are visible yet.
          </p>
        ) : (
          <>
            {priceInsights.map((insight) => (
              <div
                key={`${insight.merchant}-${insight.itemName}`}
                className="rounded-xl border border-border/30 bg-surface-muted/15 p-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text">
                    {insight.itemName}
                  </p>
                  <Badge variant={priceInsightBadgeVariant(insight.signalType)}>
                    {priceInsightBadgeLabel(insight.signalType)}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-text-muted">
                  {insight.merchant} · {formatCurrency(insight.latestPrice)} now
                  versus {formatCurrency(insight.previousPrice)} on{' '}
                  {insight.previousDate}
                </p>
                {insight.latestUnitLabel || insight.previousUnitLabel ? (
                  <p className="mt-1 text-xs text-text-muted">
                    Size: {insight.latestUnitLabel ?? 'Unknown'} now versus{' '}
                    {insight.previousUnitLabel ?? 'Unknown'} before
                    {insight.sizeChangePct != null
                      ? ` (${formatPercent(insight.sizeChangePct, {
                          decimals: 0,
                          sign: true,
                          nullDisplay: '—',
                        })})`
                      : ''}
                  </p>
                ) : null}
                {insight.latestUnitPrice != null &&
                insight.previousUnitPrice != null ? (
                  <p className="mt-1 text-xs text-text-muted">
                    Unit price:{' '}
                    {formatCurrency(insight.latestUnitPrice, {
                      decimals: 2,
                    })}{' '}
                    now versus{' '}
                    {formatCurrency(insight.previousUnitPrice, {
                      decimals: 2,
                    })}{' '}
                    before
                    {insight.unitPriceChangePct != null
                      ? ` (${formatPercent(insight.unitPriceChangePct, {
                          decimals: 0,
                          sign: true,
                          nullDisplay: '—',
                        })})`
                      : ''}
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-text-muted">
                    Ticket price change:{' '}
                    {signedCurrency(insight.priceChange, {
                      decimals: 2,
                    })}
                  </p>
                )}
                <p className="mt-2 text-sm leading-relaxed text-text-muted">
                  {insight.recommendation}
                </p>
              </div>
            ))}

            {merchantHighlights.map((merchant) => (
              <div
                key={merchant.merchant}
                className="rounded-xl border border-border/30 bg-surface-muted/15 p-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text">
                    {merchant.merchant}
                  </p>
                  <span className="text-sm font-semibold tabular-nums text-text">
                    {formatCurrencyWhole(merchant.totalSpend)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-text-muted">
                  {merchant.transactionCount} purchase
                  {merchant.transactionCount === 1 ? '' : 's'} ·{' '}
                  {formatEnumLabel(merchant.cadence)}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-text-muted">
                  {merchant.recommendation}
                </p>
              </div>
            ))}
          </>
        )}
      </div>
    </SectionCard>
  )
}
