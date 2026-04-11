'use client'

import { AlertCircle, ArrowRight, RefreshCw } from 'lucide-react'
import Link from 'next/link'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { SymbolDecisionPanel } from '@/components/symbol/SymbolDecisionPanel'
import { SymbolWorkflowPanel } from '@/components/symbol/SymbolWorkflowPanel'
import { Button } from '@/components/ui/button'
import { ThesisSection } from '@/components/watchlist/ThesisSection'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import { useJennyDashboard } from '@/lib/hooks/usePortfolio'
import { usePreferences } from '@/lib/hooks/usePreferences'
import { useSymbolIntelligence } from '@/lib/hooks/useSymbolIntelligence'
import { cn, formatRelativeTime } from '@/lib/utils'
import {
  compareNotifications,
  formatCountLabel,
  formatEvidenceSummary,
  formatIfNotHeldReasoning,
  formatNewsSentimentSummary,
  formatPortfolioWeight,
  formatShareCount,
} from './symbol-formatters'

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
  const jennyAlertCount =
    currentDecision?.sourceKind === 'jenny_alert'
      ? Math.max(symbolNotifications.length, 1)
      : symbolNotifications.length
  const alertCount = (data?.alerts.length ?? 0) + jennyAlertCount
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
      ? `Invested portfolio has ${data.portfolio.context.numHoldings} holding${data.portfolio.context.numHoldings === 1 ? '' : 's'}`
      : null,
    data?.portfolio?.context?.concentrationTop3 != null
      ? `Top 3 invested holdings make up ${formatPercent(data.portfolio.context.concentrationTop3)}`
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
  const decisionUsesLiveModel =
    currentDecision?.sourceKind === 'live_signal_model'

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
        <SectionCard variant="surface" title="Current Decision">
          <p className="font-display italic text-2xl text-text">
            {currentDecision?.headline ?? '—'}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            {currentDecision?.summary ??
              'No live recommendation summary is available yet.'}
          </p>
          {decisionUsesLiveModel ? (
            <p className="mt-3 text-sm text-text">
              Score {data?.scores?.overall?.toFixed(0) ?? '—'} ·{' '}
              {formatEnumLabel(data?.signal?.type, 'Unavailable')} · Strength{' '}
              {data?.signal?.strength ?? '—'}/10
            </p>
          ) : (
            <p className="mt-3 text-sm text-text">
              Live signal {formatEnumLabel(data?.signal?.type, 'Unavailable')}{' '}
              · Strength {data?.signal?.strength ?? '—'}/10
            </p>
          )}
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
              <SymbolDecisionPanel
                symbol={uppercaseSymbol}
                data={data}
                activeNotification={activeNotification}
                latestReview={latestReview}
                tradeReviews={tradeReviews}
                positionSummary={positionSummary}
                portfolioContextParts={portfolioContextParts}
              />
            ),
          },
          {
            value: 'track',
            label: 'Track',
            badge: alertCount > 0 ? String(alertCount) : undefined,
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
                    {activeNotification ? (
                      <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4">
                        <p className="text-sm font-semibold text-text">
                          Current Jenny alert
                        </p>
                        <p className="mt-2 text-sm text-text">
                          {activeNotification.title}
                        </p>
                        <p className="mt-2 text-sm text-text-muted">
                          {activeNotification.recommendation ??
                            activeNotification.detail ??
                            'This open alert is still driving the current decision.'}
                        </p>
                        <p className="mt-3 text-xs uppercase tracking-[0.18em] text-text-muted">
                          {formatEnumLabel(activeNotification.severity, 'Info')}
                          {activeNotification.createdAt
                            ? ` · ${formatRelativeTime(activeNotification.createdAt)}`
                            : ''}
                        </p>
                      </div>
                    ) : null}
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
                      href="/portfolio?tab=holdings&highlight=concentration#portfolio-overview"
                      className="group flex items-center justify-between rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text transition-all duration-200 hover:border-primary/40 hover:bg-surface-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      <span>Current portfolio concentration</span>
                      <ArrowRight className="h-4 w-4 text-text-muted transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary" />
                    </Link>
                    <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                      <AlertCircle className="mb-2 h-4 w-4 text-primary" />
                      Thesis, position size, and review history are available
                      on this symbol workspace.
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
