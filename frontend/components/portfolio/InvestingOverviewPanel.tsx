'use client'

import { ChevronDown, ExternalLink, Newspaper, Target } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { IndicatorsTrendChart } from '@/components/market/IndicatorsTrendChart'
import { MarketStatusBadge } from '@/components/market/MarketStatusBadge'
import { SectorPerformanceChart } from '@/components/market/SectorPerformanceChart'
import { SentimentTrendChart } from '@/components/market/SentimentTrendChart'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import type { NewsBundle } from '@/lib/api/news'
import type { PositionWithValue } from '@/lib/api/portfolio'
import type { SentimentArticle, WatchlistItem } from '@/lib/api/watchlist'
import { formatPercent } from '@/lib/formatters'
import { useMarketIntelligence } from '@/lib/hooks/useMarketIntelligence'
import { useNewsIntelligence } from '@/lib/hooks/useNews'
import { cn, formatRelativeTime } from '@/lib/utils'

const MARKET_CONTEXT_STORAGE_KEY = 'portfolio-ai:investing-market-context-open'
const MAX_HEADLINES = 5

type RelevantHeadline = {
  id: string
  headline: string
  detail: string
  href: string
  external: boolean
  label: string
  tone: 'positive' | 'neutral' | 'negative'
  publishedAt?: string | null
  source?: string | null
}

function toneForArticle(article: SentimentArticle | undefined) {
  const label = article?.sentiment?.label?.toLowerCase()
  if (label === 'positive') {
    return 'positive' as const
  }
  if (label === 'negative') {
    return 'negative' as const
  }
  return 'neutral' as const
}

function headlineDetail(article: SentimentArticle | undefined) {
  return (
    article?.actionableInsight ||
    article?.impactSummary ||
    article?.summary ||
    'Applicable context is still building for this headline.'
  )
}

function formatIndicatorValue(value: number | null | undefined, suffix = '') {
  if (value == null || Number.isNaN(value)) {
    return '—'
  }

  return `${value.toFixed(suffix ? 2 : 1)}${suffix}`
}

function buildRelevantHeadlines({
  watchlistItems,
  heldSymbols,
  marketNews,
}: {
  watchlistItems: WatchlistItem[]
  heldSymbols: Set<string>
  marketNews?: NewsBundle
}) {
  const symbolEntries = watchlistItems
    .map((item) => {
      const article = item.recentNews?.articles?.[0]
      if (!article) {
        return null
      }

      const symbol = item.symbol.toUpperCase()
      const isHeld = heldSymbols.has(symbol)
      const priorityBoost =
        (isHeld ? 100 : 0) +
        (item.scoreAlert ? 35 : 0) +
        (item.signalStrength ?? 0)

      return {
        id: `symbol-${symbol}-${article.contentHash}`,
        headline: article.headline,
        detail: headlineDetail(article),
        href: `/symbols/${symbol}`,
        external: false,
        label: isHeld ? `Held · ${symbol}` : `Watchlist · ${symbol}`,
        tone: toneForArticle(article),
        publishedAt: article.publishedAt,
        source: article.source,
        priorityBoost,
      }
    })
    .filter((entry): entry is NonNullable<typeof entry> => Boolean(entry))
    .sort((left, right) => {
      if (right.priorityBoost !== left.priorityBoost) {
        return right.priorityBoost - left.priorityBoost
      }
      return (
        new Date(right.publishedAt ?? 0).getTime() -
        new Date(left.publishedAt ?? 0).getTime()
      )
    })

  const selected: RelevantHeadline[] = symbolEntries
    .slice(0, MAX_HEADLINES)
    .map(({ priorityBoost: _priorityBoost, ...entry }) => entry)

  if (selected.length >= MAX_HEADLINES) {
    return selected
  }

  const seenHeadlines = new Set(selected.map((entry) => entry.headline))
  const marketEntries = (marketNews?.articles ?? [])
    .filter((article) => !seenHeadlines.has(article.headline))
    .map((article) => ({
      id: `market-${article.contentHash}`,
      headline: article.headline,
      detail: headlineDetail(article),
      href: article.url ?? '/portfolio',
      external: Boolean(article.url),
      label: 'Market',
      tone: toneForArticle(article),
      publishedAt: article.publishedAt,
      source: article.source,
    }))

  return [...selected, ...marketEntries].slice(0, MAX_HEADLINES)
}

function PulseValue({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="min-w-0 rounded-xl border border-border/30 bg-surface-muted/20 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
        {label}
      </p>
      <p className="mt-1 truncate text-sm font-semibold tabular-nums text-text">
        {value}
      </p>
    </div>
  )
}

function toneClasses(tone: RelevantHeadline['tone']) {
  if (tone === 'positive') {
    return 'bg-gain'
  }
  if (tone === 'negative') {
    return 'bg-loss'
  }
  return 'bg-text-muted'
}

export function InvestingOverviewPanel({
  watchlistItems,
  positions,
}: {
  watchlistItems: WatchlistItem[]
  positions: PositionWithValue[]
}) {
  const [isOpen, setIsOpen] = useState(true)
  const { data: market, isLoading: marketLoading } = useMarketIntelligence()
  const { data: marketNews } = useNewsIntelligence(undefined, {
    limit: 12,
    enabled: isOpen,
  })
  const heldSymbols = useMemo(
    () => new Set(positions.map((position) => position.symbol.toUpperCase())),
    [positions],
  )

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    const storedValue = window.localStorage.getItem(MARKET_CONTEXT_STORAGE_KEY)
    if (storedValue == null) {
      setIsOpen(true)
      return
    }

    setIsOpen(storedValue === 'true')
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.localStorage.setItem(MARKET_CONTEXT_STORAGE_KEY, String(isOpen))
  }, [isOpen])

  const relevantHeadlines = useMemo(
    () =>
      buildRelevantHeadlines({
        watchlistItems,
        heldSymbols,
        marketNews,
      }),
    [heldSymbols, marketNews, watchlistItems],
  )

  const pulseSummary =
    market?.narrative ||
    'Open market context to review mood, benchmarks, sector trends, and the headlines that matter.'
  const fearGreedValue = market
    ? `${market.fearGreed.label} (${Math.round(market.fearGreed.score)})`
    : 'Loading…'
  const sp500Value = market?.indicators.sp500
    ? formatPercent(market.indicators.sp500.changePct ?? 0, { sign: true })
    : '—'
  const vixValue = formatIndicatorValue(market?.indicators.vix?.value)
  const tnxValue = formatIndicatorValue(market?.indicators.tnx?.value, '%')

  return (
    <SectionCard
      variant="surface"
      padding="none"
      className="overflow-hidden"
      contentClassName="p-0"
    >
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <button
            id="portfolio-overview"
            type="button"
            className="w-full px-6 py-5 text-left transition-colors hover:bg-surface-muted/15"
            aria-label="Toggle market context"
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-display italic text-lg tracking-tight text-text">
                    Market Pulse
                  </p>
                  <MarketStatusBadge />
                  <Badge variant="outline">
                    {isOpen ? 'Context open' : 'Context collapsed'}
                  </Badge>
                </div>
                <p className="max-w-4xl text-sm leading-relaxed text-text-muted">
                  {pulseSummary}
                </p>
              </div>
              <div className="flex items-center gap-2 text-sm font-medium text-text-muted">
                <span>{isOpen ? 'Hide charts' : 'Open charts'}</span>
                <ChevronDown
                  className={cn(
                    'h-4 w-4 transition-transform',
                    isOpen && 'rotate-180',
                  )}
                />
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <PulseValue label="Market Mood" value={fearGreedValue} />
              <PulseValue label="S&P 500" value={sp500Value} />
              <PulseValue label="Volatility" value={vixValue} />
              <PulseValue label="10-Year Rate" value={tnxValue} />
            </div>

            {!marketLoading && market?.lastUpdated ? (
              <p className="mt-3 text-xs text-text-muted">
                Updated {formatRelativeTime(market.lastUpdated)}
              </p>
            ) : null}
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="border-t border-border/40 px-6 py-6">
            <div className="grid gap-6 xl:grid-cols-2">
              <SectionCard variant="ghost" padding="none">
                <SentimentTrendChart />
              </SectionCard>

              <SectionCard variant="ghost" padding="none">
                <IndicatorsTrendChart />
              </SectionCard>

              <SectionCard variant="ghost" padding="none">
                <SectorPerformanceChart />
              </SectionCard>

              <SectionCard
                title="Relevant Headlines"
                description="Held names first, then broader market context."
                variant="ghost"
                padding="none"
              >
                {relevantHeadlines.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/15 px-5 py-10 text-sm text-text-muted">
                    No relevant headlines yet. Refresh symbols or market data to
                    repopulate this view.
                  </div>
                ) : (
                  <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface-muted/15">
                    {relevantHeadlines.map((headline, index) => {
                      return (
                        <div
                          key={headline.id}
                          className={cn(
                            'px-5 py-4',
                            index !== 0 && 'border-t border-border/30',
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <span
                                  className={cn(
                                    'mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full',
                                    toneClasses(headline.tone),
                                  )}
                                />
                                <Badge variant="outline">{headline.label}</Badge>
                              </div>
                              {headline.external ? (
                                <a
                                  href={headline.href}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-start gap-2 text-sm font-semibold leading-relaxed text-text transition-colors hover:text-primary"
                                >
                                  <span className="line-clamp-2">
                                    {headline.headline}
                                  </span>
                                  <ExternalLink className="mt-0.5 h-4 w-4 shrink-0" />
                                </a>
                              ) : (
                                <Link
                                  href={headline.href}
                                  className="inline-flex items-start gap-2 text-sm font-semibold leading-relaxed text-text transition-colors hover:text-primary"
                                >
                                  <span className="line-clamp-2">
                                    {headline.headline}
                                  </span>
                                  <Target className="mt-0.5 h-4 w-4 shrink-0" />
                                </Link>
                              )}
                              <p className="line-clamp-2 text-sm leading-relaxed text-text-muted">
                                {headline.detail}
                              </p>
                            </div>
                            <Newspaper className="mt-1 h-4 w-4 shrink-0 text-text-muted/60" />
                          </div>
                          <p className="mt-2 text-xs text-text-muted">
                            {[headline.source, headline.publishedAt
                              ? formatRelativeTime(headline.publishedAt)
                              : null]
                              .filter(Boolean)
                              .join(' · ')}
                          </p>
                        </div>
                      )
                    })}
                  </div>
                )}
              </SectionCard>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </SectionCard>
  )
}
