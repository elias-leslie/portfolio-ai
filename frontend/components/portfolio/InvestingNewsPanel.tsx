'use client'

import { ExternalLink, Newspaper, Target } from 'lucide-react'
import Link from 'next/link'
import { useMemo } from 'react'
import { Badge } from '@/components/ui/badge'
import { SectionCard } from '@/components/shared/SectionCard'
import type { NewsBundle } from '@/lib/api/news'
import type { PositionWithValue } from '@/lib/api/portfolio'
import type { SentimentArticle, WatchlistItem } from '@/lib/api/watchlist'
import { useNewsIntelligence } from '@/lib/hooks/useNews'
import { cn, formatRelativeTime } from '@/lib/utils'

type HeadlineTone = 'positive' | 'neutral' | 'negative'

type RelevantHeadline = {
  id: string
  headline: string
  detail: string
  href: string
  external: boolean
  tone: HeadlineTone
  badge: string
  symbol?: string
  publishedAt?: string | null
  source?: string | null
}

type HeadlineGroup = {
  id: 'held' | 'watching' | 'market'
  title: string
  description: string
  items: RelevantHeadline[]
}

const MAX_HEADLINES_PER_GROUP = 5

function toneForArticle(article: SentimentArticle | undefined): HeadlineTone {
  const label = article?.sentiment?.label?.toLowerCase()
  if (label === 'positive') {
    return 'positive'
  }
  if (label === 'negative') {
    return 'negative'
  }
  return 'neutral'
}

function headlineDetail(article: SentimentArticle | undefined) {
  return (
    article?.actionableInsight ||
    article?.impactSummary ||
    article?.summary ||
    'Applicable context is still building for this headline.'
  )
}

function toneDotClasses(tone: HeadlineTone) {
  if (tone === 'positive') {
    return 'bg-gain'
  }
  if (tone === 'negative') {
    return 'bg-loss'
  }
  return 'bg-text-muted'
}

function buildHeadlineGroups({
  watchlistItems,
  heldSymbols,
  marketNews,
}: {
  watchlistItems: WatchlistItem[]
  heldSymbols: Set<string>
  marketNews?: NewsBundle
}): HeadlineGroup[] {
  const symbolHeadlines = watchlistItems
    .map((item) => {
      const article = item.recentNews?.articles?.[0]
      if (!article) {
        return null
      }

      const symbol = item.symbol.toUpperCase()
      const held = heldSymbols.has(symbol)

      return {
        item,
        symbol,
        held,
        article,
        priority:
          (held ? 100 : 0) +
          (item.scoreAlert ? 35 : 0) +
          (item.signalStrength ?? 0),
      }
    })
    .filter((entry): entry is NonNullable<typeof entry> => Boolean(entry))
    .sort((left, right) => {
      if (right.priority !== left.priority) {
        return right.priority - left.priority
      }
      return (
        new Date(right.article.publishedAt ?? 0).getTime() -
        new Date(left.article.publishedAt ?? 0).getTime()
      )
    })

  const seen = new Set<string>()
  const toHeadline = (
    article: SentimentArticle,
    groupLabel: string,
    symbol?: string,
  ): RelevantHeadline => {
    const href =
      symbol && !article.url ? `/symbols/${symbol}` : article.url ?? '/portfolio'
    return {
      id: `${groupLabel.toLowerCase()}-${symbol ?? 'market'}-${article.contentHash}`,
      headline: article.headline,
      detail: headlineDetail(article),
      href,
      external: Boolean(article.url),
      tone: toneForArticle(article),
      badge: symbol ?? 'Market',
      symbol,
      publishedAt: article.publishedAt,
      source: article.source,
    }
  }

  const heldItems = symbolHeadlines
    .filter((entry) => entry.held)
    .slice(0, MAX_HEADLINES_PER_GROUP)
    .map((entry) => {
      seen.add(entry.article.headline)
      return toHeadline(entry.article, 'Held', entry.symbol)
    })

  const watchingItems = symbolHeadlines
    .filter((entry) => !entry.held && !seen.has(entry.article.headline))
    .slice(0, MAX_HEADLINES_PER_GROUP)
    .map((entry) => {
      seen.add(entry.article.headline)
      return toHeadline(entry.article, 'Watching', entry.symbol)
    })

  const marketItems = (marketNews?.articles ?? [])
    .filter((article) => !seen.has(article.headline))
    .slice(0, MAX_HEADLINES_PER_GROUP)
    .map((article) => toHeadline(article, 'Market'))

  const groups: HeadlineGroup[] = [
    {
      id: 'held',
      title: 'Held',
      description: 'News tied directly to positions you already own.',
      items: heldItems,
    },
    {
      id: 'watching',
      title: 'Watching',
      description: 'Signals and headlines tied to names you are tracking.',
      items: watchingItems,
    },
    {
      id: 'market',
      title: 'Market',
      description: 'Broad headlines only when they change the backdrop.',
      items: marketItems,
    },
  ]

  return groups.filter((group) => group.items.length > 0)
}

function HeadlineGroupCard({ group }: { group: HeadlineGroup }) {
  return (
    <SectionCard
      title={group.title}
      description={group.description}
      variant="surface"
      padding="none"
      className="overflow-hidden"
    >
      <div className="overflow-hidden">
        {group.items.map((headline, index) => {
          const headlineContent = (
            <>
              <span className="line-clamp-2">{headline.headline}</span>
              {headline.external ? (
                <ExternalLink className="mt-0.5 h-4 w-4 shrink-0" />
              ) : (
                <Target className="mt-0.5 h-4 w-4 shrink-0" />
              )}
            </>
          )

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
                        toneDotClasses(headline.tone),
                      )}
                    />
                    <Badge variant="outline">{headline.badge}</Badge>
                  </div>

                  {headline.external ? (
                    <a
                      href={headline.href}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-start gap-2 text-sm font-semibold leading-relaxed text-text transition-colors hover:text-primary"
                    >
                      {headlineContent}
                    </a>
                  ) : (
                    <Link
                      href={headline.href}
                      className="inline-flex items-start gap-2 text-sm font-semibold leading-relaxed text-text transition-colors hover:text-primary"
                    >
                      {headlineContent}
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
    </SectionCard>
  )
}

export function InvestingNewsPanel({
  watchlistItems,
  positions,
}: {
  watchlistItems: WatchlistItem[]
  positions: PositionWithValue[]
}) {
  const { data: marketNews } = useNewsIntelligence(undefined, { limit: 24 })
  const heldSymbols = useMemo(
    () => new Set(positions.map((position) => position.symbol.toUpperCase())),
    [positions],
  )
  const groups = useMemo(
    () =>
      buildHeadlineGroups({
        watchlistItems,
        heldSymbols,
        marketNews,
      }),
    [heldSymbols, marketNews, watchlistItems],
  )

  if (groups.length === 0) {
    return (
      <SectionCard
        title="News"
        description="Applicable headlines will appear here once market or symbol news is available."
        variant="surface"
      >
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/15 px-5 py-10 text-sm text-text-muted">
          No relevant headlines yet. Refresh symbols or market data to
          repopulate this view.
        </div>
      </SectionCard>
    )
  }

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      {groups.map((group) => (
        <HeadlineGroupCard key={group.id} group={group} />
      ))}
    </div>
  )
}
