'use client'

import { ExternalLink, Loader2, ThumbsDown, ThumbsUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useArticleFeedback, useSubmitArticleFeedback } from '@/lib/hooks/useNews'
import {
  formatConfidence,
  formatNewsDate,
  formatSentimentScore,
  formatVendorLabel,
  getSentimentBadgeVariant,
  getSentimentScoreOrUndefined,
} from '@/lib/utils/news-formatting'
import type { NewsArticle } from './news-card/types'

interface NewsArticleCardProps {
  article: NewsArticle
  index: number
}

/**
 * Individual news article card with sentiment display.
 * Normalizes data from different news source structures.
 */
export function NewsArticleCard({ article, index }: NewsArticleCardProps) {
  // Normalize article data from either structure
  const sentimentScore = getSentimentScoreOrUndefined(article)
  const sentimentLabel = article.sentimentLabel ?? article.sentiment?.label
  const sentimentConfidence = article.sentiment?.confidence
  const sentimentModel = article.sentiment?.model

  const timeAgo = formatNewsDate(article.publishedAt)
  const source =
    article.source && article.source.trim().length > 0
      ? article.source.trim()
      : formatVendorLabel(article.vendor)

  const displayHeadline = article.headline
  const articleHash = article.articleHash ?? article.contentHash ?? null
  const canRateArticle = Boolean(article.url && articleHash && article.vendor)
  const { data: feedback } = useArticleFeedback(articleHash ?? undefined, {
    enabled: canRateArticle,
  })
  const submitFeedback = useSubmitArticleFeedback()
  const isSubmittingFeedback =
    submitFeedback.isPending &&
    submitFeedback.variables?.articleHash === articleHash
  const currentFeedback = feedback?.exists ? feedback.isUseful : undefined

  // Generate unique key
  const articleKey =
    article.articleHash ||
    article.contentHash ||
    article.url ||
    `article-${index}-${article.headline.substring(0, 30)}`

  return (
    <div
      key={articleKey}
      className="rounded-xl border border-border/40 bg-surface-muted/20 p-4 transition-colors duration-150 hover:border-border/60 hover:bg-surface-muted/30"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex-1 space-y-1">
          {article.url ? (
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline"
            >
              {displayHeadline}
              <ExternalLink className="h-3 w-3" />
            </a>
          ) : (
            <p className="text-sm font-semibold text-text">{displayHeadline}</p>
          )}
          <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted">
            {article.vendor && (
              <Badge
                variant="outline"
                className="text-[10px] font-semibold uppercase tracking-wide"
              >
                {formatVendorLabel(article.vendor)}
              </Badge>
            )}
            {source && <span className="text-text">Publisher: {source}</span>}
            {timeAgo && <span>{timeAgo}</span>}
          </div>
        </div>
        <div className="flex flex-col items-end gap-2 text-xs">
          {article.qualityConfidence !== undefined &&
            article.qualityConfidence !== null && (
              <Badge
                variant={
                  article.qualityConfidence >= 0.7
                    ? 'success'
                    : article.qualityConfidence >= 0.5
                      ? 'warning'
                      : 'secondary'
                }
                className="text-[10px]"
              >
                Quality {Math.round(article.qualityConfidence * 100)}%
              </Badge>
            )}
          {article.isPrimaryArticle && (
            <Badge variant="success" className="text-[10px]">
              Primary
            </Badge>
          )}
          {article.coverageCount && article.coverageCount > 1 && (
            <Badge variant="secondary" className="text-[10px]">
              {article.coverageCount} sources
            </Badge>
          )}
          {sentimentLabel && (
            <Badge variant={getSentimentBadgeVariant(sentimentLabel)}>
              {sentimentLabel.toUpperCase()}
            </Badge>
          )}
          {sentimentScore !== undefined && sentimentScore !== null && (
            <span className="text-text font-semibold tabular-nums">
              {formatSentimentScore(sentimentScore)}
            </span>
          )}
          {sentimentConfidence !== undefined &&
            sentimentConfidence !== null && (
              <span className="text-text-muted">
                Confidence {formatConfidence(sentimentConfidence)}
              </span>
            )}
          {sentimentModel && (
            <Badge
              variant={sentimentModel === 'finbert' ? 'secondary' : 'loss'}
            >
              {sentimentModel.toUpperCase()}
            </Badge>
          )}
        </div>
      </div>
      {canRateArticle ? (
        <div className="mt-3 flex items-center justify-between gap-3 border-t border-border/40 pt-3">
          <span className="text-xs text-text-muted">
            {currentFeedback === true
              ? 'Marked useful'
              : currentFeedback === false
                ? 'Marked not useful'
                : 'Was this useful?'}
          </span>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              size="sm"
              variant={currentFeedback === true ? 'default' : 'outline'}
              className="h-8 px-2"
              aria-label="Mark article as useful"
              aria-pressed={currentFeedback === true}
              disabled={isSubmittingFeedback}
              onClick={() =>
                submitFeedback.mutate({
                  articleUrl: article.url ?? '',
                  articleHash: articleHash ?? '',
                  vendor: article.vendor ?? '',
                  isUseful: true,
                })
              }
            >
              {isSubmittingFeedback && currentFeedback !== false ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <ThumbsUp className="h-3.5 w-3.5" />
              )}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={currentFeedback === false ? 'default' : 'outline'}
              className="h-8 px-2"
              aria-label="Mark article as not useful"
              aria-pressed={currentFeedback === false}
              disabled={isSubmittingFeedback}
              onClick={() =>
                submitFeedback.mutate({
                  articleUrl: article.url ?? '',
                  articleHash: articleHash ?? '',
                  vendor: article.vendor ?? '',
                  isUseful: false,
                })
              }
            >
              {isSubmittingFeedback && currentFeedback !== true ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <ThumbsDown className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
