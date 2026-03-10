'use client'

import { AlertCircle, ArrowRight, RefreshCw } from 'lucide-react'
import Link from 'next/link'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { useJennyDashboard } from '@/lib/hooks/usePortfolio'
import { useSymbolIntelligence } from '@/lib/hooks/useSymbolIntelligence'
import { SymbolWorkflowPanel } from '@/components/symbol/SymbolWorkflowPanel'
import { ThesisSection } from '@/components/watchlist/ThesisSection'

function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '—'
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '—'
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

export function SymbolWorkspace({ symbol }: { symbol: string }) {
  const uppercaseSymbol = symbol.toUpperCase()
  const { data, isLoading, error, refetch, isFetching } = useSymbolIntelligence(
    uppercaseSymbol,
  )
  const { data: jennyDashboard } = useJennyDashboard()
  const latestReview = jennyDashboard?.symbolReviews.find(
    (review) => review.symbol === uppercaseSymbol,
  )
  const tradeReviews =
    jennyDashboard?.tradeReviews.filter((review) => review.symbol === uppercaseSymbol) ?? []

  if (isLoading) {
    return (
      <PageContainer className="space-y-10 py-10">
        <PageHeader title={uppercaseSymbol} description="Loading symbol workspace..." />
        <div className="grid gap-4 lg:grid-cols-4">
          {[...Array(4)].map((_, index) => (
            <div
              key={`symbol-skeleton-${index}`}
              className="h-32 animate-pulse rounded-2xl bg-surface-muted/40"
            />
          ))}
        </div>
      </PageContainer>
    )
  }

  if (error || data?.error) {
    return (
      <PageContainer className="space-y-10 py-10">
        <PageHeader title={uppercaseSymbol} description="Symbol workspace" />
        <SectionCard variant="surface">
          <div className="rounded-2xl border border-loss/30 bg-loss/10 p-5 text-sm text-loss">
            Failed to load symbol intelligence.
          </div>
        </SectionCard>
      </PageContainer>
    )
  }

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        eyebrow="Symbol Workspace"
        title={uppercaseSymbol}
        description="One place for the live setup, thesis, Jenny review, and the practical next step."
        actions={
          <>
            <Button asChild variant="outline">
              <Link href="/watchlist">Back to Watchlist</Link>
            </Button>
            <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-4">
        <SectionCard variant="surface" title="Overall Score">
          <p className="text-3xl font-semibold text-text">
            {data?.scores?.overall?.toFixed(0) ?? '—'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Signal {data?.signal?.type ?? 'Unavailable'} · Strength{' '}
            {data?.signal?.strength ?? '—'}/10
          </p>
        </SectionCard>
        <SectionCard variant="surface" title="Recommendation">
          <p className="text-2xl font-semibold text-text">
            {data?.recommendation?.action?.replaceAll('_', ' ') ?? '—'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            {data?.recommendation?.reasoning?.[0] ?? 'No recommendation summary yet.'}
          </p>
        </SectionCard>
        <SectionCard variant="surface" title="Position">
          <p className="text-2xl font-semibold text-text">
            {data?.portfolio?.held ? formatCurrency(data.portfolio.position?.currentValue) : 'Not held'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            {data?.portfolio?.held
              ? `${formatPercent(data.portfolio.position?.gainPct)} · ${formatPercent(data.portfolio.position?.weightPct)} of portfolio`
              : data?.recommendation?.ifNotHeld?.reasoning ?? 'Jenny does not see a live portfolio position.'}
          </p>
        </SectionCard>
        <SectionCard variant="surface" title="Market Backdrop">
          <p className="text-2xl font-semibold text-text">
            {data?.market?.fearGreedLabel ?? '—'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Fear & Greed {data?.market?.fearGreedScore ?? '—'} · VIX{' '}
            {data?.market?.vix?.toFixed(1) ?? '—'}
          </p>
        </SectionCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <SectionCard
          variant="surface"
          title="Decision Memo"
          description="The clearest plain-language case for acting, waiting, or stepping aside."
        >
          <div className="space-y-4">
            {(data?.recommendation?.reasoning ?? []).map((reason) => (
              <div
                key={reason}
                className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text-muted"
              >
                {reason}
              </div>
            ))}
            {data?.trading ? (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Entry / Stop
                  </p>
                  <p className="mt-2 text-sm text-text">
                    {formatCurrency(data.trading.entryPrice)} / {formatCurrency(data.trading.stopLoss)}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Target / Size
                  </p>
                  <p className="mt-2 text-sm text-text">
                    {formatCurrency(data.trading.profitTarget)} / {data.trading.positionSizeShares ?? '—'} shares
                  </p>
                </div>
              </div>
            ) : null}
            {data?.recommendation?.ifNotHeld ? (
              <div className="rounded-2xl border border-border/40 bg-primary/5 p-4 text-sm text-text">
                If not held: {data.recommendation.ifNotHeld.action ?? 'Review'} ·{' '}
                {data.recommendation.ifNotHeld.reasoning}
              </div>
            ) : null}
          </div>
        </SectionCard>

        <SectionCard
          variant="surface"
          title="Jenny Review Loop"
          description="Latest operator review and what the outcome history is teaching."
        >
          <div className="space-y-4">
            {latestReview ? (
              <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
                <p className="text-sm font-semibold text-text">
                  Current verdict: {latestReview.finalVerdict}
                </p>
                <p className="mt-2 text-sm text-text-muted">
                  {latestReview.reasons[0] ?? 'Jenny has a review but no short summary yet.'}
                </p>
                {latestReview.managementDetail ? (
                  <p className="mt-3 text-sm text-text">{latestReview.managementDetail}</p>
                ) : null}
              </div>
            ) : (
              <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text-muted">
                Jenny has not published a symbol review for {uppercaseSymbol} yet.
              </div>
            )}

            {tradeReviews.length > 0 ? (
              tradeReviews.slice(0, 2).map((review) => (
                <div
                  key={review.id}
                  className="rounded-2xl border border-border/40 bg-surface/60 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-text">
                      Outcome: {review.outcomeLabel}
                    </p>
                    <span className="text-xs text-text-muted">
                      {formatPercent(review.returnPct)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">{review.lesson}</p>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                No completed outcome reviews yet. The next closed-loop value here comes after live ideas are reviewed through time.
              </div>
            )}
          </div>
        </SectionCard>
      </div>

      <SymbolWorkflowPanel symbol={uppercaseSymbol} />

      <ThesisSection symbol={uppercaseSymbol} userTimezone="America/New_York" />

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <SectionCard
          variant="surface"
          title="News and Alerts"
          description={data?.news?.headline ?? 'Latest headlines and alert signals.'}
        >
          <div className="space-y-3">
            {data?.alerts?.length ? (
              <div className="flex flex-wrap gap-2">
                {data.alerts.map((alert) => (
                  <span
                    key={`${alert.icon}-${alert.label}`}
                    className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1 text-xs font-semibold text-text"
                  >
                    {alert.label}
                  </span>
                ))}
              </div>
            ) : null}

            {(data?.news?.keyEvents ?? []).length > 0 ? (
              data?.news?.keyEvents.map((event) => (
                <div
                  key={`${event.text}-${event.timeAgo}`}
                  className="rounded-2xl border border-border/40 bg-surface/60 p-4"
                >
                  <p className="text-sm font-medium text-text">{event.text}</p>
                  <p className="mt-1 text-xs text-text-muted">{event.timeAgo}</p>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                No recent key events attached to this symbol right now.
              </div>
            )}
          </div>
        </SectionCard>

        <SectionCard
          variant="surface"
          title="Next Step"
          description="Push the symbol back into the main operating loop."
        >
          <div className="grid gap-3">
            <Link
              href="/watchlist"
              className="flex items-center justify-between rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text transition hover:border-primary/40"
            >
              <span>Review this symbol in the watchlist context</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/portfolio"
              className="flex items-center justify-between rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text transition hover:border-primary/40"
            >
              <span>Compare the idea against current portfolio concentration</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
            <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
              <AlertCircle className="mb-2 h-4 w-4 text-primary" />
              The point of this page is to keep thesis, sizing, and review context in one place before you act.
            </div>
          </div>
        </SectionCard>
      </div>
    </PageContainer>
  )
}
