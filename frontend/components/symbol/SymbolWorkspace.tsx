'use client'

import { AlertCircle, ArrowRight, ExternalLink, RefreshCw } from 'lucide-react'
import Link from 'next/link'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { RelativeTime } from '@/components/shared/RelativeTime'
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
import { useMarketIntelligence } from '@/lib/hooks/useMarketIntelligence'
import { useJennyDashboard, usePortfolio } from '@/lib/hooks/usePortfolio'
import { usePreferences } from '@/lib/hooks/usePreferences'
import {
  useRefreshSymbolIntelligence,
  useSymbolIntelligence,
} from '@/lib/hooks/useSymbolIntelligence'
import { cn, formatDate } from '@/lib/utils'
import {
  compareNotifications,
  formatCountLabel,
  formatEvidenceSummary,
  formatIfNotHeldReasoning,
  formatNewsSentimentSummary,
  formatPortfolioWeight,
  formatShareCount,
} from './symbol-formatters'

function safeArticleUrl(value: string | null | undefined) {
  if (!value) {
    return null
  }

  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
      ? url.toString()
      : null
  } catch {
    return null
  }
}

export function SymbolWorkspace({ symbol }: { symbol: string }) {
  const uppercaseSymbol = symbol.toUpperCase()
  const { data, isLoading, error, isFetching } =
    useSymbolIntelligence(uppercaseSymbol)
  const refreshSymbol = useRefreshSymbolIntelligence(uppercaseSymbol)
  const { data: jennyDashboard, error: jennyError } = useJennyDashboard()
  const { data: preferences } = usePreferences()
  const userTimezone = preferences?.displayTimezone ?? 'America/New_York'

  // Progressive hydration: fill the Position and Market Context cards from
  // standalone hooks immediately, while the monolithic symbol-intelligence
  // call (which feeds Decision + Quote) is still resolving.
  const { data: portfolioData } = usePortfolio()
  const { data: marketIntel } = useMarketIntelligence()
  const earlyPosition =
    portfolioData?.positions?.find(
      (position) => position.symbol.toUpperCase() === uppercaseSymbol,
    ) ?? null
  const portfolioTotalValue = portfolioData?.totalValue ?? null
  const earlyVixIndicator = marketIntel?.indicators
    ? Object.values(marketIntel.indicators).find(
        (indicator) =>
          indicator.shortLabel?.toUpperCase().includes('VIX') ||
          indicator.label?.toUpperCase().includes('VIX'),
      )
    : undefined
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
  const quote = data?.quote ?? null
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
      : error || data?.error
        ? 'Position status is temporarily unavailable from symbol intelligence.'
        : 'Jenny does not see a live portfolio position.'
  const decisionUsesLiveModel =
    currentDecision?.sourceKind === 'live_signal_model'
  const entrySignalAction =
    data?.recommendation?.ifNotHeld?.action ?? data?.signal?.type
  const entrySignalParts = [
    entrySignalAction ? formatEnumLabel(entrySignalAction, 'Review') : null,
    data?.scores?.overall != null
      ? `Score ${data.scores.overall.toFixed(0)}`
      : null,
    data?.signal?.type ? `${formatEnumLabel(data.signal.type)} signal` : null,
    data?.signal?.strength != null
      ? `Strength ${data.signal.strength}/10`
      : null,
  ].filter((part): part is string => Boolean(part))
  const entrySignalSummary =
    decisionUsesLiveModel && entrySignalParts.length > 0
      ? `${data?.portfolio?.held ? 'Entry signal if not held' : 'Live entry signal'}: ${entrySignalParts.join(' · ')}`
      : null
  const marketAsOfDate =
    data?.market?.sp500AsOfDate ??
    data?.market?.vixAsOfDate ??
    data?.market?.fearGreedAsOfDate ??
    null
  const isRefreshingSymbol = isFetching || refreshSymbol.isPending
  const quoteDetailParts = [
    quote?.source ? quote.source : null,
    quote?.session ? formatEnumLabel(quote.session) : null,
    quote?.freshnessLabel ?? null,
  ].filter((part): part is string => Boolean(part))
  const monolithUnavailable = Boolean(error || data?.error)
  const sectionIssues = data?.sectionIssues ?? []
  const unavailableSections = new Set(
    sectionIssues.map((issue) => issue.section),
  )
  const newsUnavailable =
    !data?.news &&
    (monolithUnavailable ||
      unavailableSections.has('news') ||
      unavailableSections.has('watchlist'))

  // Decision + Quote come only from the monolithic call; show per-card
  // skeletons for just those while the standalone-hydrated cards fill.
  const monolithPending = isLoading && !data

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
              onClick={() => {
                refreshSymbol.mutate()
              }}
              disabled={isRefreshingSymbol}
              aria-busy={isRefreshingSymbol}
            >
              <RefreshCw
                className={cn(
                  'mr-2 h-4 w-4',
                  isRefreshingSymbol && 'animate-spin',
                )}
              />
              Refresh
            </Button>
          </>
        }
      />

      {monolithUnavailable ? (
        <div
          role="status"
          className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning"
        >
          <p className="font-semibold">Symbol intelligence is incomplete.</p>
          <p className="mt-1">
            Scores, quote, or recommendation data could not be refreshed.
            Independent position and market context are still shown when
            available.
          </p>
        </div>
      ) : sectionIssues.length > 0 ? (
        <div
          role="status"
          className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning"
        >
          <p className="font-semibold">
            Some symbol intelligence is temporarily unavailable.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {sectionIssues.map((issue) => (
              <li key={`${issue.section}-${issue.message}`}>{issue.message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {jennyError ? (
        <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Jenny review data is temporarily unavailable. Live symbol intelligence
          is still shown below.
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 text-xs text-text-muted">
        <span className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1">
          {data?.generatedAt ? (
            <>
              Updated <RelativeTime value={data.generatedAt} />
            </>
          ) : (
            'Update time unavailable'
          )}
        </span>
        {quote?.cachedAt ? (
          <span className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1">
            Quote <RelativeTime value={quote.cachedAt} />
          </span>
        ) : null}
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

      <div className="grid gap-4 lg:grid-cols-4 animate-stagger">
        <SectionCard variant="surface" title="Current Decision">
          {monolithPending ? (
            <div className="skeleton h-24 rounded-lg" />
          ) : (
            <>
              <p className="font-display italic text-2xl text-text">
                {currentDecision?.headline ?? '—'}
              </p>
              <p className="mt-2 text-sm text-text-muted">
                {currentDecision?.sourceLabel ?? 'Decision source unavailable'}
                {currentDecision?.sourceTimestamp ? (
                  <>
                    {' · '}
                    <RelativeTime value={currentDecision.sourceTimestamp} />
                  </>
                ) : null}
              </p>
              {entrySignalSummary ? (
                <p
                  className="mt-3 text-sm text-text"
                  title="Plain-English: suggested action, scanner score (0–100), signal type, and model conviction (Strength, 1–10)."
                >
                  {entrySignalSummary}
                </p>
              ) : (
                <p
                  className="mt-3 text-sm text-text"
                  title="Strength is the model's conviction, from 1 (weak) to 10 (strong)."
                >
                  Live signal{' '}
                  {formatEnumLabel(data?.signal?.type, 'Unavailable')} ·
                  Strength {data?.signal?.strength ?? '—'}/10
                </p>
              )}
              {currentDecision?.severity ? (
                <p className="mt-2 text-xs uppercase tracking-[0.18em] text-text-muted">
                  {formatEnumLabel(currentDecision.severity, 'Info')}
                </p>
              ) : null}
            </>
          )}
        </SectionCard>
        <SectionCard variant="surface" title="Current Quote">
          {monolithPending ? (
            <div className="skeleton h-24 rounded-lg" />
          ) : (
            <>
              <p className="font-display italic text-2xl tabular-nums text-text">
                {formatCurrency(quote?.price)}
              </p>
              <p className="mt-2 text-sm text-text-muted">
                {quoteDetailParts.length > 0
                  ? quoteDetailParts.join(' · ')
                  : 'Canonical quote unavailable'}
              </p>
              {quote?.cachedAt ? (
                <p className="mt-2 text-xs uppercase tracking-[0.16em] text-text-muted">
                  As of <RelativeTime value={quote.cachedAt} />
                </p>
              ) : null}
              {quote?.error ? (
                <p className="mt-2 text-xs text-warning">{quote.error}</p>
              ) : null}
            </>
          )}
        </SectionCard>
        <SectionCard variant="surface" title="Your Position">
          {data?.portfolio ? (
            <>
              <p className="font-display italic text-2xl tabular-nums text-text">
                {data.portfolio.held
                  ? formatCurrency(heldPosition?.currentValue)
                  : 'Not held'}
              </p>
              <p className="mt-2 text-sm text-text-muted">{positionSummary}</p>
              {portfolioContextParts.length > 0 ? (
                <p className="mt-2 text-sm text-text-muted">
                  {portfolioContextParts.join(' · ')}
                </p>
              ) : null}
            </>
          ) : earlyPosition ? (
            <>
              <p className="font-display italic text-2xl tabular-nums text-text">
                {formatCurrency(earlyPosition.currentValue)}
              </p>
              <p className="mt-2 text-sm text-text-muted">
                {[
                  formatShareCount(earlyPosition.shares),
                  earlyPosition.gainPct != null
                    ? formatPercent(earlyPosition.gainPct, { sign: true })
                    : null,
                  portfolioTotalValue
                    ? formatPortfolioWeight(
                        (earlyPosition.currentValue / portfolioTotalValue) *
                          100,
                      )
                    : null,
                ]
                  .filter((part): part is string => Boolean(part))
                  .join(' · ') || 'Live position details unavailable.'}
              </p>
            </>
          ) : monolithPending ? (
            <div className="skeleton h-24 rounded-lg" />
          ) : (
            <>
              <p className="font-display italic text-2xl tabular-nums text-text">
                {monolithUnavailable ? 'Unavailable' : 'Not held'}
              </p>
              <p className="mt-2 text-sm text-text-muted">{positionSummary}</p>
            </>
          )}
        </SectionCard>
        <SectionCard variant="surface" title="Market Context">
          {data?.market ? (
            <>
              <p className="font-display italic text-2xl tabular-nums text-text">
                {data.market.fearGreedLabel ?? '—'}
              </p>
              <p
                className="mt-2 text-sm text-text-muted"
                title="Fear & Greed runs 0 (extreme fear) to 100 (extreme greed). VIX is expected market volatility — higher means more fear."
              >
                Daily Fear & Greed {data.market.fearGreedScore ?? '—'}/100 · VIX{' '}
                {data.market.vix?.toFixed(1) ?? '—'}
              </p>
              {data.market.sector ? (
                <p className="mt-2 text-sm text-text-muted">
                  {data.market.sector.name ?? 'Sector unavailable'} ·{' '}
                  {data.market.sector.signal ?? 'No sector signal'} ·{' '}
                  {formatPercent(data.market.sector.relativeToSpy, {
                    sign: true,
                  })}{' '}
                  vs SPY over latest close
                </p>
              ) : data.market.sp500Change != null ? (
                <p className="mt-2 text-sm text-text-muted">
                  S&P 500 latest close · 1D{' '}
                  {formatPercent(data.market.sp500Change, { sign: true })}
                </p>
              ) : null}
              <p className="mt-2 text-xs uppercase tracking-[0.16em] text-text-muted">
                {marketAsOfDate ? (
                  `Latest daily close through ${formatDate(marketAsOfDate)}`
                ) : data?.generatedAt ? (
                  <>
                    As of <RelativeTime value={data.generatedAt} />
                  </>
                ) : (
                  'As-of time unavailable'
                )}
              </p>
            </>
          ) : marketIntel?.fearGreed ? (
            <>
              <p className="font-display italic text-2xl tabular-nums text-text">
                {marketIntel.fearGreed.label ?? '—'}
              </p>
              <p
                className="mt-2 text-sm text-text-muted"
                title="Fear & Greed runs 0 (extreme fear) to 100 (extreme greed). VIX is expected market volatility — higher means more fear."
              >
                Fear & Greed {marketIntel.fearGreed.score ?? '—'}/100
                {earlyVixIndicator?.value != null
                  ? ` · VIX ${earlyVixIndicator.value.toFixed(1)}`
                  : ''}
              </p>
              <p className="mt-2 text-xs uppercase tracking-[0.16em] text-text-muted">
                Live market snapshot
              </p>
            </>
          ) : monolithPending ? (
            <div className="skeleton h-24 rounded-lg" />
          ) : (
            <p className="text-sm text-text-muted">
              Market context unavailable
            </p>
          )}
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
                      : newsUnavailable
                        ? 'News context is temporarily unavailable; existing Jenny alerts remain visible.'
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
                          {activeNotification.createdAt ? (
                            <>
                              {' · '}
                              <RelativeTime
                                value={activeNotification.createdAt}
                              />
                            </>
                          ) : null}
                        </p>
                      </div>
                    ) : null}
                    {data?.news ? (
                      <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                        {formatNewsSentimentSummary(data.news)}
                        {' · '}
                        {data.news.articleCount24H ?? 0} article
                        {data.news.articleCount24H === 1 ? '' : 's'} in the last
                        24h
                      </div>
                    ) : newsUnavailable ? (
                      <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
                        News data is temporarily unavailable. Existing Jenny
                        alerts are still shown.
                      </div>
                    ) : (
                      <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                        No recent news summary is available for this symbol.
                      </div>
                    )}
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
                        {newsUnavailable
                          ? 'Recent key events are temporarily unavailable.'
                          : 'No recent key events attached to this symbol right now.'}
                      </div>
                    )}
                    {(data?.news?.recentArticles ?? []).length > 0 ? (
                      <div className="space-y-3">
                        <p className="text-sm font-semibold text-text">
                          Recent articles
                        </p>
                        {data?.news?.recentArticles
                          .slice(0, 4)
                          .map((article, idx) => {
                            const articleUrl = safeArticleUrl(article.url)
                            return (
                              <div
                                key={`${article.headline}-${article.publishedAt ?? idx}`}
                                className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                              >
                                {articleUrl ? (
                                  <a
                                    href={articleUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-start gap-2 text-sm font-medium text-text underline-offset-4 transition-colors hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                                  >
                                    <span>{article.headline}</span>
                                    <ExternalLink
                                      className="mt-0.5 h-3.5 w-3.5 shrink-0"
                                      aria-hidden
                                    />
                                  </a>
                                ) : (
                                  <p className="text-sm font-medium text-text">
                                    {article.headline}
                                  </p>
                                )}
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
                            )
                          })}
                      </div>
                    ) : (data?.news?.articleCount24H ?? 0) > 0 ? (
                      <div className="rounded-2xl border border-dashed border-border/40 bg-surface/40 p-4 text-sm text-text-muted">
                        Article volume is available, but this snapshot did not
                        attach recent headlines yet.
                      </div>
                    ) : null}
                  </div>
                </SectionCard>

                <SectionCard variant="surface" title="Put This In Context">
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
                      Thesis, position size, and review history are available on
                      this symbol workspace.
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
