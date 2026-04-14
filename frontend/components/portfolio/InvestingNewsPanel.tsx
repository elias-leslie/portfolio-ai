'use client'

import { ExternalLink, Newspaper, Target } from 'lucide-react'
import Link from 'next/link'
import { useMemo } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
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
  id: 'holdings' | 'watchlist' | 'marketContext'
  title: string
  description: string
  items: RelevantHeadline[]
}

type MacroTopic = {
  detail: string
  label: string
  patterns: RegExp[]
}

const MAX_HEADLINES_PER_GROUP = 5
const SOURCE_SUFFIX_PATTERN =
  /\s[-|:]\s(?:yahoo finance|marketwatch|the motley fool|motley fool|seeking alpha|reuters|bloomberg|investor'?s business daily|benzinga)\s*$/i
const GENERIC_ACTIONABLE_INSIGHTS = new Set([
  'news reported - read the details before acting',
  'positive sentiment - worth investigating',
  'negative sentiment - proceed with caution',
])
const GENERIC_IMPACT_SUMMARIES = new Set([
  'news reported - assess impact based on your strategy',
  'very positive news - may create short-term momentum',
  'mildly positive - modest upside possible',
  'very negative news - may trigger selling pressure',
  'mildly negative - modest downside risk',
])
const MARKET_CONTEXT_SOURCE_ALLOWLIST = new Set([
  'Associated Press',
  'Barron’s',
  "Barron's",
  'Bloomberg',
  'CNBC',
  'Financial Times',
  "Investor's Business Daily",
  'MarketWatch',
  'Reuters',
  'The Wall Street Journal',
  'Wall Street Journal',
  'Yahoo Finance',
])
const NON_SIGNAL_PATTERNS = [
  /\bstocks?\s+to\s+buy\b/i,
  /\bshould\s+you\s+buy\b/i,
  /\bbest\s+\w+\s+(?:stocks?|reits?|etfs?|funds?)\b/i,
  /\bretirement income\b/i,
  /\bhigh-yield\b/i,
  /\bdividend\b/i,
  /\bfully valued\b/i,
  /\bworth investigating\b/i,
  /\bdilution risk\b/i,
  /\bi would trust\b/i,
  /\bprice target\b/i,
  /\btop pick\b/i,
  /\bmy top\b/i,
  /\bstrong buy\b/i,
  /\bstill holds true\b/i,
  /\bwhat should i do\b/i,
  /\bmy husband\b/i,
  /\bmistake you can make\b/i,
  /\bmissing the point\b/i,
  /\bunder trump\b/i,
  /\bwith \$\d[\d,]*\b/i,
  /\b(?:travel|retirement|income)\b/i,
]
const MACRO_TOPICS: MacroTopic[] = [
  {
    label: 'Rates',
    detail:
      'Changes discount-rate pressure across growth stocks, broad indexes, and valuation multiples.',
    patterns: [
      /\bfed\b/i,
      /\bpowell\b/i,
      /\brates?\b/i,
      /\btreasur(?:y|ies)\b/i,
      /\byields?\b/i,
      /\bcentral bank\b/i,
      /\becb\b/i,
      /\bbank of japan\b/i,
      /\bboj\b/i,
    ],
  },
  {
    label: 'Inflation',
    detail:
      'Can shift rate expectations, bond yields, and equity multiples across the portfolio.',
    patterns: [/\binflation\b/i, /\bcpi\b/i, /\bppi\b/i, /\bpce\b/i],
  },
  {
    label: 'Growth',
    detail:
      'Changes recession or soft-landing odds and resets broad earnings expectations.',
    patterns: [
      /\bjobs?\b/i,
      /\bpayrolls?\b/i,
      /\bunemployment\b/i,
      /\bgdp\b/i,
      /\brecession\b/i,
      /\beconom(?:y|ic)\b/i,
      /\bconsumer spending\b/i,
      /\bretail sales\b/i,
      /\bhousing\b/i,
    ],
  },
  {
    label: 'Risk',
    detail:
      'Signals whether risk appetite is strengthening or tightening across many holdings at once.',
    patterns: [
      /\bvix\b/i,
      /\bshort-covering\b/i,
      /\brisk[- ]on\b/i,
      /\brisk[- ]off\b/i,
      /\bshaky footing\b/i,
      /\bmarket breadth\b/i,
      /\bstock market\b/i,
      /\bwall street\b/i,
      /\bs&p(?:\s+500)?\b/i,
      /\bnasdaq\b/i,
      /\bdow\b/i,
      /\brussell\b/i,
    ],
  },
  {
    label: 'Sector Leadership',
    detail:
      'Shows whether market leadership is broadening or narrowing across major sectors and index weights.',
    patterns: [
      /\bsoftware stocks?\b/i,
      /\bsemiconductors?\b/i,
      /\bbanks?\b/i,
      /\benergy stocks?\b/i,
      /\bsector\b/i,
      /\bbuy areas\b/i,
      /\bchart of the day\b/i,
    ],
  },
  {
    label: 'Geopolitics',
    detail:
      'Can reprice energy, shipping, defense, and broad market risk premiums very quickly.',
    patterns: [
      /\biran\b/i,
      /\boil\b/i,
      /\bcrude\b/i,
      /\bopec\b/i,
      /\btariffs?\b/i,
      /\btrade war\b/i,
      /\bgeopolit(?:ic|ical)\b/i,
    ],
  },
]

function matchesAnyPattern(text: string, patterns: RegExp[]) {
  return patterns.some((pattern) => pattern.test(text))
}

function cleanText(value?: string | null) {
  if (!value) {
    return ''
  }
  return value
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/\s+/g, ' ')
    .trim()
}

function normalizedText(value: string) {
  return cleanText(value)
    .normalize('NFKD')
    .replace(/[\u2018\u2019]/g, "'")
    .replace(SOURCE_SUFFIX_PATTERN, '')
    .replace(/[^a-z0-9\s]/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

function articleDecisionScore(article: SentimentArticle) {
  return article.decisionValueScore ?? null
}

function canonicalHeadline(article: SentimentArticle) {
  return normalizedText(article.canonicalHeadline ?? article.headline)
}

function articleContext(article: SentimentArticle) {
  return [
    cleanText(article.headline),
    cleanText(article.summary),
    cleanText(article.impactSummary),
    cleanText(article.actionableInsight),
  ]
    .filter(Boolean)
    .join(' ')
}

function hasGenericFallbackCopy(article: SentimentArticle) {
  const actionable = normalizedText(article.actionableInsight ?? '')
  const impact = normalizedText(article.impactSummary ?? '')
  return (
    (!actionable || GENERIC_ACTIONABLE_INSIGHTS.has(actionable)) &&
    (!impact || GENERIC_IMPACT_SUMMARIES.has(impact))
  )
}

function hasSubstantiveSummary(article: SentimentArticle) {
  return cleanText(article.summary).length >= 80
}

function isQuestionableArticle(article: SentimentArticle) {
  return matchesAnyPattern(articleContext(article), NON_SIGNAL_PATTERNS)
}

function detailForSymbolArticle(article: SentimentArticle) {
  const decisionReason = cleanText(article.decisionValueReason)
  if (decisionReason) {
    return decisionReason
  }

  const actionable = cleanText(article.actionableInsight)
  if (
    actionable &&
    !GENERIC_ACTIONABLE_INSIGHTS.has(normalizedText(actionable))
  ) {
    return actionable
  }

  const impact = cleanText(article.impactSummary)
  if (impact && !GENERIC_IMPACT_SUMMARIES.has(normalizedText(impact))) {
    return impact
  }

  const summary = cleanText(article.summary)
  if (summary) {
    return summary
  }

  return 'New development tied to this symbol.'
}

function macroTopicForArticle(article: SentimentArticle) {
  if (article.marketContextTopic) {
    return (
      MACRO_TOPICS.find(
        (topic) => topic.label === article.marketContextTopic,
      ) ?? {
        label: article.marketContextTopic,
        detail:
          cleanText(article.decisionValueReason) || cleanText(article.summary),
        patterns: [],
      }
    )
  }
  if (isQuestionableArticle(article)) {
    return null
  }
  const context = articleContext(article)
  if (!context) {
    return null
  }
  return (
    MACRO_TOPICS.find((topic) => matchesAnyPattern(context, topic.patterns)) ??
    null
  )
}

function shouldSurfaceSymbolArticle(article: SentimentArticle) {
  const decisionScore = articleDecisionScore(article)
  if (decisionScore !== null) {
    return decisionScore >= 0.55
  }
  if (isQuestionableArticle(article)) {
    return false
  }
  return (
    article.isMaterialEvent === true ||
    article.qualityPrediction === true ||
    !hasGenericFallbackCopy(article)
  )
}

function shouldSurfaceMacroArticle(article: SentimentArticle) {
  const decisionScore = articleDecisionScore(article)
  if (decisionScore !== null) {
    return (
      Boolean(article.marketContextTopic) &&
      decisionScore >= 0.6 &&
      article.sourceSignalTier !== 'commentary'
    )
  }
  const topic = macroTopicForArticle(article)
  if (!topic) {
    return false
  }
  if (!MARKET_CONTEXT_SOURCE_ALLOWLIST.has(cleanText(article.source))) {
    return false
  }
  return article.qualityPrediction === true || hasSubstantiveSummary(article)
}

function bestSymbolArticle(articles: SentimentArticle[] | undefined) {
  const candidates = (articles ?? []).filter(shouldSurfaceSymbolArticle)
  if (candidates.length === 0) {
    return null
  }

  return [...candidates].sort((left, right) => {
    const rightScore = articleDecisionScore(right) ?? -1
    const leftScore = articleDecisionScore(left) ?? -1
    if (rightScore !== leftScore) {
      return rightScore - leftScore
    }

    const rightQuality = right.qualityConfidence ?? 0
    const leftQuality = left.qualityConfidence ?? 0
    if (rightQuality !== leftQuality) {
      return rightQuality - leftQuality
    }

    return (
      new Date(right.publishedAt ?? 0).getTime() -
      new Date(left.publishedAt ?? 0).getTime()
    )
  })[0]
}

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
  if (!article) {
    return 'Applicable context is still building for this headline.'
  }
  return (
    detailForSymbolArticle(article) ||
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
      const article = bestSymbolArticle(item.recentNews?.articles)
      if (!article || !shouldSurfaceSymbolArticle(article)) {
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
    options?: { badge?: string; detail?: string },
  ): RelevantHeadline => {
    const href =
      symbol && !article.url
        ? `/symbols/${symbol}`
        : (article.url ?? '/portfolio')
    return {
      id: `${groupLabel.toLowerCase()}-${symbol ?? 'market'}-${article.contentHash}`,
      headline: article.headline,
      detail: options?.detail ?? headlineDetail(article),
      href,
      external: Boolean(article.url),
      tone: toneForArticle(article),
      badge: options?.badge ?? symbol ?? groupLabel,
      symbol,
      publishedAt: article.publishedAt,
      source: article.source,
    }
  }

  const heldItems: RelevantHeadline[] = []
  for (const entry of symbolHeadlines) {
    if (!entry.held || heldItems.length >= MAX_HEADLINES_PER_GROUP) {
      continue
    }
    const canonical = canonicalHeadline(entry.article)
    if (seen.has(canonical)) {
      continue
    }
    seen.add(canonical)
    heldItems.push(toHeadline(entry.article, 'Holdings', entry.symbol))
  }

  const watchingItems: RelevantHeadline[] = []
  for (const entry of symbolHeadlines) {
    if (entry.held || watchingItems.length >= MAX_HEADLINES_PER_GROUP) {
      continue
    }
    const canonical = canonicalHeadline(entry.article)
    if (seen.has(canonical)) {
      continue
    }
    seen.add(canonical)
    watchingItems.push(toHeadline(entry.article, 'Watchlist', entry.symbol))
  }

  const marketContextItems: RelevantHeadline[] = []
  for (const article of marketNews?.articles ?? []) {
    if (marketContextItems.length >= MAX_HEADLINES_PER_GROUP) {
      break
    }
    const canonical = canonicalHeadline(article)
    if (seen.has(canonical) || !shouldSurfaceMacroArticle(article)) {
      continue
    }
    seen.add(canonical)
    const topic = macroTopicForArticle(article)
    marketContextItems.push(
      toHeadline(article, 'Market Context', undefined, {
        badge: topic?.label ?? 'Market Context',
        detail:
          cleanText(article.decisionValueReason) ||
          topic?.detail ||
          cleanText(article.summary),
      }),
    )
  }

  const groups: HeadlineGroup[] = [
    {
      id: 'holdings',
      title: 'Holdings',
      description:
        'Only new developments tied directly to positions you already own.',
      items: heldItems,
    },
    {
      id: 'watchlist',
      title: 'Watchlist',
      description:
        'Only symbol-specific developments worth revisiting on names you are tracking.',
      items: watchingItems,
    },
    {
      id: 'marketContext',
      title: 'Market Context',
      description:
        'Macro and regime changes only when they can affect multiple holdings at once.',
      items: marketContextItems,
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
                {[
                  headline.source,
                  headline.publishedAt
                    ? formatRelativeTime(headline.publishedAt)
                    : null,
                ]
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
        description="This panel stays quiet unless the news is specific to your holdings, watchlist, or market context."
        variant="surface"
      >
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/15 px-5 py-10 text-sm text-text-muted">
          Nothing decision-useful right now. Duplicated, generic, and
          non-portfolio headlines stay hidden on purpose.
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
