'use client'

import { AlertCircle, ArrowRight, RefreshCw } from 'lucide-react'
import Link from 'next/link'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { Button } from '@/components/ui/button'
import { useJennyDashboard } from '@/lib/hooks/usePortfolio'
import { usePreferences } from '@/lib/hooks/usePreferences'
import { useSymbolIntelligence } from '@/lib/hooks/useSymbolIntelligence'
import { cn, formatRelativeTime } from '@/lib/utils'
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
  const { data: jennyDashboard, error: jennyError } = useJennyDashboard()
  const { data: preferences } = usePreferences()
  const userTimezone = preferences?.displayTimezone ?? 'America/New_York'
  const latestReview = jennyDashboard?.symbolReviews.find(
    (review) => review.symbol === uppercaseSymbol,
  )
  const tradeReviews =
    jennyDashboard?.tradeReviews.filter((review) => review.symbol === uppercaseSymbol) ?? []
  const newsArticleCount = data?.news?.recentArticles.length ?? 0
  const alertCount = data?.alerts.length ?? 0

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
        <PageHeader
          title={uppercaseSymbol}
          description="Symbol workspace"
          actions={
            <Button asChild variant="outline">
              <Link href="/watchlist">Back to Watchlist</Link>
            </Button>
          }
        />
        <SectionCard variant="surface">
          <LoadErrorState
            title="Failed to load symbol intelligence."
            detail="Retry to refresh the symbol score, recommendation, and linked workflow context."
            onRetry={() => {
              void refetch()
            }}
            isRetrying={isFetching}
          />
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
            <Button
              variant="outline"
              onClick={() => refetch()}
              disabled={isFetching}
              aria-busy={isFetching}
            >
              <RefreshCw className={cn('mr-2 h-4 w-4', isFetching && 'animate-spin')} />
              Refresh
            </Button>
          </>
        }
      />

      {jennyError ? (
        <SectionCard variant="surface">
          <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
            Jenny review data is temporarily unavailable. Live symbol intelligence is still shown
            below.
          </div>
        </SectionCard>
      ) : null}

      <div className="rounded-xl border border-border/30 border-l-primary/50 border-l-2 bg-gradient-to-r from-primary/[0.04] to-surface/40 px-4 py-3 text-sm text-text-muted">
        {data?.generatedAt
          ? `Updated ${formatRelativeTime(data.generatedAt)}`
          : 'Update time unavailable'}
        {' · '}
        {alertCount} alert{alertCount === 1 ? '' : 's'}
        {' · '}
        {newsArticleCount} recent article{newsArticleCount === 1 ? '' : 's'}
        {' · '}
        {data?.news?.articleCount24H ?? 0} article
        {data?.news?.articleCount24H === 1 ? '' : 's'} in 24h
        {' · '}
        {data?.signal?.confirmations ?? 0} confirmation
        {data?.signal?.confirmations === 1 ? '' : 's'}
        {' · '}
        {data?.signal?.avoidFlags ?? 0} avoid flag
        {data?.signal?.avoidFlags === 1 ? '' : 's'}
      </div>

      <div className="grid gap-4 lg:grid-cols-4 animate-stagger">
        <SectionCard variant="surface" title="Overall Score">
          <p className="font-display italic text-3xl tabular-nums text-text">
            {data?.scores?.overall?.toFixed(0) ?? '—'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Signal {data?.signal?.type ?? 'Unavailable'} · Strength{' '}
            {data?.signal?.strength ?? '—'}/10
          </p>
          <p className="mt-2 text-sm text-text-muted">
            {data?.signal?.confirmations ?? 0} confirmations · {data?.signal?.avoidFlags ?? 0}{' '}
            avoid flags
          </p>
        </SectionCard>
        <SectionCard variant="surface" title="Recommendation">
          <p className="font-display italic text-2xl uppercase text-text">
            {data?.recommendation?.action?.replaceAll('_', ' ') ?? '—'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            {data?.recommendation?.reasoning?.[0] ?? 'No recommendation summary yet.'}
          </p>
        </SectionCard>
        <SectionCard variant="surface" title="Position">
          <p className="font-display italic text-2xl tabular-nums text-text">
            {data?.portfolio?.held ? formatCurrency(data.portfolio.position?.currentValue) : 'Not held'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            {data?.portfolio?.held
              ? `${formatPercent(data.portfolio.position?.gainPct)} · ${formatPercent(data.portfolio.position?.weightPct)} of portfolio`
              : data?.recommendation?.ifNotHeld?.reasoning ?? 'Jenny does not see a live portfolio position.'}
          </p>
          {data?.portfolio?.context ? (
            <p className="mt-2 text-sm text-text-muted">
              {data.portfolio.context.numHoldings} holding
              {data.portfolio.context.numHoldings === 1 ? '' : 's'} · Top 3{' '}
              {formatPercent(data.portfolio.context.concentrationTop3)} · Diversification{' '}
              {data.portfolio.context.diversificationScore?.toFixed(0) ?? '—'}
            </p>
          ) : null}
        </SectionCard>
        <SectionCard variant="surface" title="Market Backdrop">
          <p className="font-display italic text-2xl tabular-nums text-text">
            {data?.market?.fearGreedLabel ?? '—'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Fear & Greed {data?.market?.fearGreedScore ?? '—'} · VIX{' '}
            {data?.market?.vix?.toFixed(1) ?? '—'}
          </p>
          {data?.market?.sector ? (
            <p className="mt-2 text-sm text-text-muted">
              {data.market.sector.name ?? 'Sector unavailable'} ·{' '}
              {data.market.sector.signal ?? 'No sector signal'} ·{' '}
              {formatPercent(data.market.sector.relativeToSpy)} vs SPY
            </p>
          ) : data?.market?.sp500Change != null ? (
            <p className="mt-2 text-sm text-text-muted">
              S&P 500 {formatPercent(data.market.sp500Change)}
            </p>
          ) : null}
        </SectionCard>
      </div>

      <WorkspaceTabs
        defaultValue="decision"
        ariaLabel="Symbol workspace sections"
        tabs={[
          {
            value: 'decision',
            label: 'Decision',
            badge: data?.recommendation?.reasoning?.length ? String(data.recommendation.reasoning.length) : undefined,
            description: 'Keep the decision memo and Jenny review in one working surface.',
            content: (
              <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                <SectionCard
                  variant="surface"
                  title="Decision Memo"
                  description="The clearest plain-language case for acting, waiting, or stepping aside."
                >
                  <div className="space-y-4">
                    {(data?.recommendation?.reasoning ?? []).length > 0 ? (
                      (data?.recommendation?.reasoning ?? []).map((reason, idx) => (
                        <div
                          key={reason}
                          className="rounded-xl border border-border/30 border-l-2 border-l-accent/40 bg-surface/40 p-4 text-sm leading-relaxed text-text-muted"
                          style={{ animationDelay: `${idx * 60}ms` }}
                        >
                          {reason}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-xl border border-dashed border-border/40 bg-surface-muted/10 p-4 text-sm text-text-muted">
                        No decision memo reasoning is available yet for this symbol.
                      </div>
                    )}
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
                        <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                            Confidence / Risk
                          </p>
                          <p className="mt-2 text-sm text-text">
                            {data.trading.confidence != null
                              ? `${Math.round(data.trading.confidence * 100)}% confidence`
                              : 'Confidence unavailable'}{' '}
                            · {data.trading.riskLevel ?? 'Risk unavailable'}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                            Holding Period
                          </p>
                          <p className="mt-2 text-sm text-text">
                            {data.trading.holdingPeriod ?? '—'} · {data.trading.style ?? 'Unknown style'}
                          </p>
                        </div>
                      </div>
                    ) : null}
                    {data?.recommendation?.ifNotHeld ? (
                      <div className="rounded-2xl border border-border/40 bg-primary/5 p-4 text-sm text-text">
                        If not held: {data.recommendation.ifNotHeld.action ?? 'Review'} ·{' '}
                        {data.recommendation.ifNotHeld.reasoning}
                        {data.recommendation.ifNotHeld.sizePct != null
                          ? ` · Size ${data.recommendation.ifNotHeld.sizePct.toFixed(1)}%`
                          : ''}
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
            ),
          },
          {
            value: 'workflow',
            label: 'Workflow',
            badge: data?.alerts.length ? String(data.alerts.length) : undefined,
            description: 'Advance the symbol, capture live-position outcomes, and keep the thesis close.',
            content: (
              <div className="space-y-6">
                <SymbolWorkflowPanel
                  symbol={uppercaseSymbol}
                  latestReview={{
                    finalVerdict: latestReview?.finalVerdict ?? null,
                    managementAction: latestReview?.managementAction ?? null,
                  }}
                />
                <ThesisSection symbol={uppercaseSymbol} userTimezone={userTimezone} />
              </div>
            ),
          },
          {
            value: 'market',
            label: 'Market',
            badge: data?.news?.articleCount24H ? String(data.news.articleCount24H) : undefined,
            description: 'Alerts, headlines, and the next routing action without forcing a long scroll.',
            content: (
              <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
                <SectionCard
                  variant="surface"
                  title="News and Alerts"
                  description={data?.news?.headline ?? 'Latest headlines and alert signals.'}
                >
                  <div className="space-y-3">
                    <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                      {data?.news?.sentimentLabel ?? 'Sentiment unavailable'}
                      {data?.news?.sentimentScore != null
                        ? ` · score ${data.news.sentimentScore.toFixed(1)}`
                        : ''}
                      {' · '}
                      {data?.news?.articleCount24H ?? 0} article
                      {data?.news?.articleCount24H === 1 ? '' : 's'} in the last 24h
                    </div>
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
                    {(data?.news?.recentArticles ?? []).length > 0 ? (
                      <div className="space-y-3">
                        <p className="text-sm font-semibold text-text">Recent articles</p>
                        {data?.news?.recentArticles.slice(0, 4).map((article, idx) => (
                          <div
                            key={`${article.headline}-${article.publishedAt ?? idx}`}
                            className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                          >
                            <p className="text-sm font-medium text-text">{article.headline}</p>
                            <p className="mt-1 text-xs text-text-muted">
                              {article.source ?? 'Unknown source'}
                              {article.publishedAt
                                ? ` · ${new Date(article.publishedAt).toLocaleString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                    hour: 'numeric',
                                    minute: '2-digit',
                                  })}`
                                : ''}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : null}
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
                      className="group flex items-center justify-between rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text transition-all duration-200 hover:border-primary/40 hover:bg-surface-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      <span>Review this symbol in the watchlist context</span>
                      <ArrowRight className="h-4 w-4 text-text-muted transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary" />
                    </Link>
                    <Link
                      href="/portfolio"
                      className="group flex items-center justify-between rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text transition-all duration-200 hover:border-primary/40 hover:bg-surface-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      <span>Compare the idea against current portfolio concentration</span>
                      <ArrowRight className="h-4 w-4 text-text-muted transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary" />
                    </Link>
                    <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                      <AlertCircle className="mb-2 h-4 w-4 text-primary" />
                      The point of this page is to keep thesis, sizing, and review context in one place before you act.
                    </div>
                  </div>
                </SectionCard>
              </div>
            ),
          },
        ]}
      />
    </PageContainer>
  )
}
