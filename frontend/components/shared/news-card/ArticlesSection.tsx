'use client'

import { Button } from '@/components/ui/button'
import { NewsArticleCard } from '../NewsArticleCard'
import type { NewsArticle, SortOption } from './types'

interface ArticlesSectionProps {
  symbol?: string | null
  articles: NewsArticle[]
  displayedArticles: NewsArticle[]
  sortedArticles: NewsArticle[]
  sortBy: SortOption
  showAll: boolean
  positiveCount: number
  negativeCount: number
  showToggleButton: boolean
  isLoadingMore: boolean
  onRequestExpanded?: () => void
  onToggleShowAll: () => void
}

export function ArticlesSection({
  symbol,
  articles,
  displayedArticles,
  sortedArticles,
  sortBy,
  showAll,
  positiveCount,
  negativeCount,
  showToggleButton,
  isLoadingMore,
  onRequestExpanded,
  onToggleShowAll,
}: ArticlesSectionProps) {
  if (articles.length === 0) {
    return (
      <div className="text-sm text-text-muted py-4">
        {symbol
          ? 'No recent articles available'
          : 'No recent market news available'}
      </div>
    )
  }

  return (
    <>
      {!showAll && sortBy === 'recent' && (
        <p className="text-xs text-text-muted mb-3">
          {positiveCount > 0 && negativeCount > 0
            ? `Showing ${positiveCount} positive + ${negativeCount} negative articles`
            : positiveCount > 0
              ? `Showing ${positiveCount} most positive articles`
              : negativeCount > 0
                ? `Showing ${negativeCount} most negative articles`
                : `Showing ${displayedArticles.length} articles`}{' '}
          ({displayedArticles.length} of {sortedArticles.length})
        </p>
      )}
      {!showAll && sortBy !== 'recent' && (
        <p className="text-xs text-text-muted mb-3">
          Showing {displayedArticles.length} of {sortedArticles.length} articles
        </p>
      )}
      <div className="space-y-2">
        {displayedArticles.map((article, idx) => (
          <NewsArticleCard
            key={
              article.articleHash ||
              article.contentHash ||
              article.url ||
              `article-${idx}-${article.headline.substring(0, 30)}`
            }
            article={article}
            index={idx}
          />
        ))}
      </div>
      {showToggleButton && (
        <div className="mt-3 flex justify-center">
          <Button
            variant="outline"
            size="sm"
            onClick={onToggleShowAll}
            className="text-xs"
            disabled={isLoadingMore}
          >
            {isLoadingMore
              ? 'Loading headlines...'
              : showAll
                ? 'Show Less'
                : onRequestExpanded
                  ? 'Load More...'
                  : `Show All (${sortedArticles.length} total)`}
          </Button>
        </div>
      )}
    </>
  )
}
