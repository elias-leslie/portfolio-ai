'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import type {
  JennyNotification,
  JennySymbolReview,
  JennyTradeReview,
} from '@/lib/api/portfolio'
import type { SymbolIntelligence } from '@/lib/api/symbols'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
  formatPnlDollars,
} from '@/lib/formatters'
import { formatRelativeTime } from '@/lib/utils'
import { formatShareCount, stripSymbolPrefix } from './symbol-formatters'

export function CurrentExposure({
  data,
  positionSummary,
  portfolioContextParts,
}: {
  data?: SymbolIntelligence | null
  positionSummary: string
  portfolioContextParts: string[]
}) {
  const position = data?.portfolio?.position ?? null

  return (
    <SectionCard variant="surface" title="Current Exposure">
      <p className="font-display italic text-2xl tabular-nums text-text">
        {data?.portfolio?.held
          ? formatCurrency(position?.currentValue)
          : 'Not held'}
      </p>
      <p className="mt-2 text-sm text-text-muted">{positionSummary}</p>
      {position ? (
        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
              Shares
            </p>
            <p className="mt-1 text-sm font-semibold text-text">
              {formatShareCount(position.shares) ?? '—'}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
              Gain/Loss
            </p>
            <p className="mt-1 text-sm font-semibold text-text">
              {formatPnlDollars(position.gain)} ·{' '}
              {formatPercent(position.gainPct, { sign: true })}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
              Weight
            </p>
            <p className="mt-1 text-sm font-semibold text-text">
              {formatPercent(position.weightPct)}
            </p>
          </div>
        </div>
      ) : null}
      {portfolioContextParts.length > 0 ? (
        <p className="mt-4 text-sm text-text-muted">
          {portfolioContextParts.join(' · ')}
        </p>
      ) : null}
    </SectionCard>
  )
}

export function SourceAuditTrail({
  symbol,
  activeNotification,
  latestReview,
  tradeReviews,
}: {
  symbol: string
  activeNotification: JennyNotification | null
  latestReview?: JennySymbolReview | null
  tradeReviews: JennyTradeReview[]
}) {
  return (
    <SectionCard
      variant="surface"
      title="Source & Audit Trail"
      description="Why this is on Today, without turning old reviews into competing instructions."
    >
      <div className="space-y-3">
        {activeNotification ? (
          <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4">
            <p className="text-sm font-semibold text-text">
              Active alert:{' '}
              {stripSymbolPrefix(activeNotification.title, symbol)}
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {activeNotification.recommendation ??
                'This open alert is the source of the current decision memo.'}
            </p>
            <p className="mt-3 text-xs uppercase tracking-[0.18em] text-text-muted">
              {formatEnumLabel(activeNotification.severity, 'Info')} ·{' '}
              {formatRelativeTime(activeNotification.createdAt)}
            </p>
          </div>
        ) : null}

        {latestReview ? (
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
            <p className="text-sm font-semibold text-text">
              Latest Jenny review: {latestReview.finalVerdict}
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {latestReview.reasons[0] ??
                'Jenny has a review but no short summary yet.'}
            </p>
            {latestReview.managementDetail ? (
              <p className="mt-3 text-sm text-text">
                {latestReview.managementDetail}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text-muted">
            No recent Jenny operator review in the last 7 days.
          </div>
        )}

        {tradeReviews.length > 0 ? (
          <details className="rounded-2xl border border-border/40 bg-surface/60 p-4">
            <summary className="cursor-pointer text-sm font-semibold text-text">
              Past outcomes ({tradeReviews.length})
            </summary>
            <div className="mt-3 space-y-3">
              {tradeReviews.slice(0, 2).map((review) => (
                <div
                  key={review.id}
                  className="rounded-xl border border-border/30 bg-surface-muted/15 p-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-text">
                      Result: {review.outcomeLabel}
                    </p>
                    <span className="text-xs text-text-muted">
                      {formatPercent(review.returnPct, { sign: true })}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">
                    {review.lesson}
                  </p>
                </div>
              ))}
            </div>
          </details>
        ) : null}
      </div>
    </SectionCard>
  )
}
