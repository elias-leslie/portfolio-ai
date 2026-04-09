'use client'

import { AlertCircle, ArrowRight, RefreshCw } from 'lucide-react'
import Link from 'next/link'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { SymbolWorkflowPanel } from '@/components/symbol/SymbolWorkflowPanel'
import { Button } from '@/components/ui/button'
import { ThesisSection } from '@/components/watchlist/ThesisSection'
import type { JennyNotification } from '@/lib/api/portfolio'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import { useJennyDashboard } from '@/lib/hooks/usePortfolio'
import { usePreferences } from '@/lib/hooks/usePreferences'
import { useSymbolIntelligence } from '@/lib/hooks/useSymbolIntelligence'
import { cn, formatRelativeTime } from '@/lib/utils'

function formatCountLabel(
  count: number,
  singular: string,
  plural = `${singular}s`,
) {
  return `${count} ${count === 1 ? singular : plural}`
}

function formatEvidenceSummary(
  confirmations?: number | null,
  avoidFlags?: number | null,
) {
  const segments: string[] = []

  if (confirmations != null) {
    segments.push(formatCountLabel(confirmations, 'green light'))
  }
  if (avoidFlags != null && (avoidFlags > 0 || confirmations != null)) {
    segments.push(formatCountLabel(avoidFlags, 'caution flag'))
  }

  return segments.length > 0 ? segments.join(' · ') : null
}

function formatTenPointConfidence(confidence?: number | null) {
  if (confidence == null) {
    return 'Confidence unavailable'
  }

  const boundedConfidence = Math.max(0, Math.min(10, confidence))
  const displayValue = Number.isInteger(boundedConfidence)
    ? boundedConfidence.toFixed(0)
    : boundedConfidence.toFixed(1)

  return `${displayValue}/10 confidence`
}

function formatShareCount(shares?: number | null) {
  if (shares == null) {
    return null
  }

  return `${shares.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: Number.isInteger(shares) ? 0 : 2,
  })} share${Math.abs(shares) === 1 ? '' : 's'}`
}

function formatPortfolioWeight(weightPct?: number | null) {
  if (weightPct == null) {
    return null
  }

  if (weightPct > 0 && weightPct < 0.1) {
    return '<0.1% of portfolio'
  }

  return `${formatPercent(weightPct)} of portfolio`
}

function formatIfNotHeldReasoning(reasoning?: string | null) {
  if (!reasoning) {
    return 'No extra context yet.'
  }

  return reasoning.replace(
    /Signal:\s*([A-Z_]+),\s*Strength:\s*(\d+(?:\.\d+)?)\/10/gi,
    (_, signalType: string, strength: string) =>
      `Current setup: ${formatEnumLabel(signalType, 'Unavailable')} · Confidence ${strength}/10`,
  )
}

function formatNewsSentimentSummary(
  news?: {
    sentimentLabel?: string | null
    sentimentScore?: number | null
  } | null,
) {
  if (news?.sentimentLabel) {
    return news.sentimentScore != null
      ? `${news.sentimentLabel} · score ${news.sentimentScore.toFixed(1)}`
      : news.sentimentLabel
  }

  if (news?.sentimentScore != null) {
    return `Sentiment score ${news.sentimentScore.toFixed(1)}`
  }

  return 'Sentiment unavailable'
}

function stripSymbolPrefix(title: string, symbol: string) {
  return title.replace(new RegExp(`^${symbol}:\\s*`, 'i'), '')
}

function compareNotifications(a: JennyNotification, b: JennyNotification) {
  const severityRank = (severity?: string | null) => {
    if (severity === 'critical') {
      return 0
    }
    if (severity === 'warning') {
      return 1
    }
    return 2
  }

  const severityDelta = severityRank(a.severity) - severityRank(b.severity)
  if (severityDelta !== 0) {
    return severityDelta
  }

  return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
}

export function SymbolWorkspace({ symbol }: { symbol: string }) {
  const uppercaseSymbol = symbol.toUpperCase()
  const { data, isLoading, error, refetch, isFetching } =
    useSymbolIntelligence(uppercaseSymbol)
  const { data: jennyDashboard, error: jennyError } = useJennyDashboard()
  const { data: preferences } = usePreferences()
  const userTimezone = preferences?.displayTimezone ?? 'America/New_York'
  const symbolNotifications = [...(jennyDashboard?.notifications ?? [])]
    .filter((notification) => notification.symbol === uppercaseSymbol)
    .sort(compareNotifications)
  const activeNotification = symbolNotifications[0] ?? null
  const latestReview = jennyDashboard?.symbolReviews.find(
    (review) => review.symbol === uppercaseSymbol,
  )
  const tradeReviews =
    jennyDashboard?.tradeReviews.filter(
      (review) => review.symbol === uppercaseSymbol,
    ) ?? []
  const currentDecision = data?.decision
  const heldPosition = data?.portfolio?.position ?? null
  const newsArticleCount = data?.news?.recentArticles.length ?? 0
  const alertCount = (data?.alerts.length ?? 0) + symbolNotifications.length
  const evidenceSummary = formatEvidenceSummary(
    data?.signal?.confirmations,
    data?.signal?.avoidFlags,
  )
  const decisionBadge =
    (currentDecision?.reasoning.length ?? 0) > 0
      ? String(currentDecision?.reasoning.length ?? 0)
      : activeNotification
        ? '1'
        : undefined
  const portfolioContextParts = [
    data?.portfolio?.context?.numHoldings != null
      ? `Portfolio has ${data.portfolio.context.numHoldings} total holding${data.portfolio.context.numHoldings === 1 ? '' : 's'}`
      : null,
    data?.portfolio?.context?.concentrationTop3 != null
      ? `Top 3 holdings make up ${formatPercent(data.portfolio.context.concentrationTop3)}`
      : null,
    data?.portfolio?.context?.diversificationScore != null
      ? `Diversification score ${data.portfolio.context.diversificationScore.toFixed(0)}`
      : null,
  ].filter((part): part is string => Boolean(part))
  const heldPositionSummary = [
    formatShareCount(heldPosition?.shares),
    heldPosition?.gainPct != null
      ? formatPercent(heldPosition.gainPct, { sign: true })
      : null,
    formatPortfolioWeight(heldPosition?.weightPct),
  ].filter((part): part is string => Boolean(part))
  const positionSummary = data?.portfolio?.held
    ? heldPositionSummary.join(' · ') || 'Live position details unavailable.'
    : data?.recommendation?.ifNotHeld?.reasoning
      ? formatIfNotHeldReasoning(data.recommendation.ifNotHeld.reasoning)
      : 'Jenny does not see a live portfolio position.'

  if (isLoading) {
    return (
      <PageContainer className="space-y-6 py-8">
        <PageHeader title={uppercaseSymbol} />
        <div className="grid gap-4 lg:grid-cols-3">
          {[...Array(4)].map((_, index) => (
            <div
              key={`symbol-skeleton-${index}`}
              className="skeleton rounded-2xl h-32"
            />
          ))}
        </div>
      </PageContainer>
    )
  }

  if (error || data?.error) {
    return (
      <PageContainer className="space-y-6 py-8">
        <PageHeader
          title={uppercaseSymbol}
          actions={
            <Button asChild variant="outline">
              <Link href="/portfolio?tab=symbols">Back to Investing</Link>
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
    <PageContainer className="space-y-6 py-8">
      <PageHeader
        eyebrow="Investing"
        title={uppercaseSymbol}
        actions={
          <>
            <Button asChild variant="outline">
              <Link href="/portfolio?tab=symbols">Back to Investing</Link>
            </Button>
            <Button
              variant="outline"
              onClick={() => refetch()}
              disabled={isFetching}
              aria-busy={isFetching}
            >
              <RefreshCw
                className={cn('mr-2 h-4 w-4', isFetching && 'animate-spin')}
              />
              Refresh
            </Button>
          </>
        }
      />

      {jennyError ? (
        <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Jenny review data is temporarily unavailable. Live symbol
          intelligence is still shown below.
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 text-xs text-text-muted">
        <span className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1">
          {data?.generatedAt
            ? `Updated ${formatRelativeTime(data.generatedAt)}`
            : 'Update time unavailable'}
        </span>
        <span className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1">
          {formatCountLabel(alertCount, 'alert')}
        </span>
        {newsArticleCount > 0 ? (
          <span className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1">
            {formatCountLabel(newsArticleCount, 'recent article')}
          </span>
        ) : null}
        {evidenceSummary ? (
          <span className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1">
            {evidenceSummary}
          </span>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-3 animate-stagger">
        <SectionCard variant="surface" title="Current Call">
          <p className="font-display italic text-2xl text-text">
            {currentDecision?.headline ?? '—'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            {currentDecision?.summary ??
              'No live recommendation summary is available yet.'}
          </p>
          <p className="mt-3 text-sm text-text">
            Score {data?.scores?.overall?.toFixed(0) ?? '—'} ·{' '}
            {formatEnumLabel(data?.signal?.type, 'Unavailable')} · Confidence{' '}
            {data?.signal?.strength ?? '—'}/10
          </p>
          <p className="mt-2 text-xs uppercase tracking-[0.18em] text-text-muted">
            {currentDecision?.sourceLabel ?? 'Decision unavailable'}
            {currentDecision?.severity
              ? ` · ${formatEnumLabel(currentDecision.severity, 'Info')}`
              : ''}
            {currentDecision?.sourceTimestamp
              ? ` · ${formatRelativeTime(currentDecision.sourceTimestamp)}`
              : ''}
          </p>
        </SectionCard>
        <SectionCard variant="surface" title="Your Position">
          <p className="font-display italic text-2xl tabular-nums text-text">
            {data?.portfolio?.held
              ? formatCurrency(heldPosition?.currentValue)
              : 'Not held'}
          </p>
          <p className="mt-2 text-sm text-text-muted">{positionSummary}</p>
          {portfolioContextParts.length > 0 ? (
            <p className="mt-2 text-sm text-text-muted">
              {portfolioContextParts.join(' · ')}
            </p>
          ) : null}
        </SectionCard>
        <SectionCard variant="surface" title="Market Context">
          <p className="font-display italic text-2xl tabular-nums text-text">
            {data?.market?.fearGreedLabel ?? '—'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Market mood {data?.market?.fearGreedScore ?? '—'}/100 · VIX{' '}
            {data?.market?.vix?.toFixed(1) ?? '—'}
          </p>
          {data?.market?.sector ? (
            <p className="mt-2 text-sm text-text-muted">
              {data.market.sector.name ?? 'Sector unavailable'} ·{' '}
              {data.market.sector.signal ?? 'No sector signal'} ·{' '}
              {formatPercent(data.market.sector.relativeToSpy, { sign: true })}{' '}
              vs SPY
            </p>
          ) : data?.market?.sp500Change != null ? (
            <p className="mt-2 text-sm text-text-muted">
              S&P 500 {formatPercent(data.market.sp500Change, { sign: true })}
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
            badge: decisionBadge,
            content: (
              <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                <SectionCard
                  variant="surface"
                  title="Why This Decision Shows Up"
                >
                  <div className="space-y-4">
                    {(currentDecision?.reasoning ?? []).length > 0 ? (
                      (currentDecision?.reasoning ?? []).map((reason, idx) => (
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
                        No decision memo reasoning is available yet for this
                        symbol.
                      </div>
                    )}
                    {data?.trading ? (
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                            Buy zone / downside limit
                          </p>
                          <p className="mt-2 text-sm tabular-nums text-text">
                            {formatCurrency(data.trading.entryPrice)} /{' '}
                            {formatCurrency(data.trading.stopLoss)}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                            Upside target / starter size
                          </p>
                          <p className="mt-2 text-sm tabular-nums text-text">
                            {formatCurrency(data.trading.profitTarget)} /{' '}
                            {data.trading.positionSizeShares ?? '—'} shares
                          </p>
                        </div>
                        <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                            Confidence / Risk
                          </p>
                          <p className="mt-2 text-sm text-text">
                            {formatTenPointConfidence(data.trading.confidence)}{' '}
                            · {data.trading.riskLevel ?? 'Risk unavailable'}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                            Typical holding time
                          </p>
                          <p className="mt-2 text-sm text-text">
                            {data.trading.holdingPeriod ?? '—'} ·{' '}
                            {data.trading.style ?? 'Unknown style'}
                          </p>
                        </div>
                      </div>
                    ) : null}
                    {data?.recommendation?.ifNotHeld ? (
                      <div className="rounded-2xl border border-border/40 bg-primary/5 p-4 text-sm text-text">
                        If you do not own it yet:{' '}
                        {formatEnumLabel(
                          data.recommendation.ifNotHeld.action,
                          'Review',
                        )}{' '}
                        ·{' '}
                        {formatIfNotHeldReasoning(
                          data.recommendation.ifNotHeld.reasoning,
                        )}
                        {data.recommendation.ifNotHeld.sizePct != null
                          ? ` · Starter size ${data.recommendation.ifNotHeld.sizePct.toFixed(1)}%`
                          : ''}
                      </div>
                    ) : null}
                  </div>
                </SectionCard>

                <SectionCard
                  variant="surface"
                  title="Jenny Review State"
                >
                  <div className="space-y-4">
                    {activeNotification ? (
                      <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4">
                        <p className="text-sm font-semibold text-text">
                          Active alert:{' '}
                          {stripSymbolPrefix(
                            activeNotification.title,
                            uppercaseSymbol,
                          )}
                        </p>
                        <p className="mt-2 text-sm text-text-muted">
                          {activeNotification.detail}
                        </p>
                        {activeNotification.recommendation ? (
                          <p className="mt-3 text-sm text-text">
                            {activeNotification.recommendation}
                          </p>
                        ) : null}
                        <p className="mt-3 text-xs uppercase tracking-[0.18em] text-text-muted">
                          {formatEnumLabel(activeNotification.severity, 'Info')}{' '}
                          · {formatRelativeTime(activeNotification.createdAt)}
                        </p>
                      </div>
                    ) : null}

                    {latestReview ? (
                      <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
                        <p className="text-sm font-semibold text-text">
                          Latest call: {latestReview.finalVerdict}
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
                      tradeReviews.slice(0, 2).map((review) => (
                        <div
                          key={review.id}
                          className="rounded-2xl border border-border/40 bg-surface/60 p-4"
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
                      ))
                    ) : (
                      <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                        No finished review outcomes yet. This section becomes
                        useful after live ideas have time to play out.
                      </div>
                    )}
                  </div>
                </SectionCard>
              </div>
            ),
          },
          {
            value: 'track',
            label: 'Track',
            badge: data?.alerts.length ? String(data.alerts.length) : undefined,
            content: (
              <div className="space-y-6">
                <SymbolWorkflowPanel
                  symbol={uppercaseSymbol}
                  latestReview={{
                    finalVerdict: latestReview?.finalVerdict ?? null,
                    managementAction: latestReview?.managementAction ?? null,
                  }}
                />
                <ThesisSection
                  symbol={uppercaseSymbol}
                  userTimezone={userTimezone}
                />

                <SectionCard
                  variant="surface"
                  title="News and Alerts"
                  description={
                    data?.news?.headline ??
                    ((data?.news?.articleCount24H ?? 0) > 0
                      ? 'Article volume is available, but recent headlines were not attached to this snapshot.'
                      : 'Latest headlines and alert signals.')
                  }
                >
                  <div className="space-y-3">
                    <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                      {formatNewsSentimentSummary(data?.news)}
                      {' · '}
                      {data?.news?.articleCount24H ?? 0} article
                      {data?.news?.articleCount24H === 1 ? '' : 's'} in the last
                      24h
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
                          <p className="text-sm font-medium text-text">
                            {event.text}
                          </p>
                          <p className="mt-1 text-xs text-text-muted">
                            {event.timeAgo}
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                        No recent key events attached to this symbol right now.
                      </div>
                    )}
                    {(data?.news?.recentArticles ?? []).length > 0 ? (
                      <div className="space-y-3">
                        <p className="text-sm font-semibold text-text">
                          Recent articles
                        </p>
                        {data?.news?.recentArticles
                          .slice(0, 4)
                          .map((article, idx) => (
                            <div
                              key={`${article.headline}-${article.publishedAt ?? idx}`}
                              className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                            >
                              <p className="text-sm font-medium text-text">
                                {article.headline}
                              </p>
                              <p className="mt-1 text-xs text-text-muted">
                                {article.source ?? 'Unknown source'}
                                {article.publishedAt
                                  ? ` · ${new Date(
                                      article.publishedAt,
                                    ).toLocaleString('en-US', {
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
                    ) : (data?.news?.articleCount24H ?? 0) > 0 ? (
                      <div className="rounded-2xl border border-dashed border-border/40 bg-surface/40 p-4 text-sm text-text-muted">
                        Article volume is available, but this snapshot did not
                        attach recent headlines yet.
                      </div>
                    ) : null}
                  </div>
                </SectionCard>

                <SectionCard
                  variant="surface"
                  title="Put This In Context"
                >
                  <div className="grid gap-3">
                    <Link
                      href="/portfolio?tab=symbols"
                      className="group flex items-center justify-between rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text transition-all duration-200 hover:border-primary/40 hover:bg-surface-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      <span>Review this symbol in the full investing list</span>
                      <ArrowRight className="h-4 w-4 text-text-muted transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary" />
                    </Link>
                    <Link
                      href="/portfolio?tab=holdings"
                      className="group flex items-center justify-between rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text transition-all duration-200 hover:border-primary/40 hover:bg-surface-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      <span>
                        Compare the idea against current portfolio concentration
                      </span>
                      <ArrowRight className="h-4 w-4 text-text-muted transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary" />
                    </Link>
                    <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                      <AlertCircle className="mb-2 h-4 w-4 text-primary" />
                      Use this page to sanity-check the thesis, position size,
                      and review history before you act.
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
