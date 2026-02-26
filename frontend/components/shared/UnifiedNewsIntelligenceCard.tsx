'use client'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  formatSentimentScore,
  getSentimentBadgeVariant,
} from '@/lib/utils/news-formatting'
import { SentimentBreakdownSection } from './SentimentBreakdownSection'
import { ArticlesSection } from './news-card/ArticlesSection'
import { KeyEventsSection } from './news-card/KeyEventsSection'
import { NewsCardHeader } from './news-card/NewsCardHeader'
import { useNewsCard } from './news-card/useNewsCard'

export type {
  KeyEvent,
  MarketNewsData,
  NewsArticle,
  NewsSentimentDetail,
  RecentNewsPayload,
  SymbolNewsIntelligence,
  UnifiedNewsIntelligenceCardProps,
} from './news-card/types'

import type { UnifiedNewsIntelligenceCardProps } from './news-card/types'

export function UnifiedNewsIntelligenceCard({
  symbol,
  newsIntelligence,
  marketNewsData,
  recentNews,
  showHeader = !!symbol,
  showSentimentBreakdown = true,
  newsHidden = false,
  title,
  onRequestExpanded,
  isLoadingMore = false,
  defaultCollapsed = false,
}: UnifiedNewsIntelligenceCardProps) {
  const {
    showAll,
    sortBy,
    setSortBy,
    isExpanded,
    setIsExpanded,
    articles,
    summary,
    sortedArticles,
    displayedArticles,
    positiveCount,
    negativeCount,
    showToggleButton,
    handleToggleShowAll,
  } = useNewsCard({ newsIntelligence, marketNewsData, recentNews, onRequestExpanded, defaultCollapsed })

  // Early returns AFTER all hooks
  if (newsHidden) return null
  if (!newsIntelligence && !marketNewsData && !recentNews) return null

  const isMarketNews = !symbol
  const cardTitle = title || (symbol ? '📰 News Intelligence' : 'Market News')

  return (
    <Card className={isMarketNews ? 'p-6 shadow-lg' : 'border-border'}>
      <NewsCardHeader
        cardTitle={cardTitle}
        isMarketNews={isMarketNews}
        isExpanded={isExpanded}
        onToggleExpanded={() => setIsExpanded((prev) => !prev)}
        sortBy={sortBy}
        onSortChange={setSortBy}
        summary={summary}
        articles={articles}
      />

      {showSentimentBreakdown && summary && (
        <SentimentBreakdownSection summary={summary} isExpanded={isExpanded} />
      )}

      {isExpanded && (
        <CardContent className={isMarketNews ? 'p-0' : 'space-y-4'}>
          {symbol && showHeader && newsIntelligence && (
            <div>
              <h4 className="text-sm font-semibold text-text mb-2">
                {newsIntelligence.headline}
              </h4>
              <div className="flex flex-wrap items-center gap-3 text-xs">
                <div>
                  <span className="text-text-muted">Sentiment: </span>
                  <Badge variant={getSentimentBadgeVariant(newsIntelligence.sentimentLabel)}>
                    {newsIntelligence.sentimentLabel} (
                    {formatSentimentScore(newsIntelligence.sentimentScore)})
                  </Badge>
                </div>
                <div className="text-text-muted">
                  {newsIntelligence.articleCount24H} articles in 24h
                </div>
              </div>
            </div>
          )}

          {symbol && newsIntelligence && (
            <KeyEventsSection keyEvents={newsIntelligence.keyEvents} />
          )}

          <ArticlesSection
            symbol={symbol}
            articles={articles}
            displayedArticles={displayedArticles}
            sortedArticles={sortedArticles}
            sortBy={sortBy}
            showAll={showAll}
            positiveCount={positiveCount}
            negativeCount={negativeCount}
            showToggleButton={showToggleButton}
            isLoadingMore={isLoadingMore}
            onRequestExpanded={onRequestExpanded}
            onToggleShowAll={handleToggleShowAll}
          />
        </CardContent>
      )}
    </Card>
  )
}
