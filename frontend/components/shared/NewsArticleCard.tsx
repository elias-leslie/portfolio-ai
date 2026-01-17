'use client'

import { ExternalLink } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  formatConfidence,
  formatNewsDate,
  formatSentimentScore,
  formatVendorLabel,
  getSentimentBadgeVariant,
  getSentimentScoreOrUndefined,
} from '@/lib/utils/news-formatting'

interface NewsArticle {
  symbol?: string
  headline: string
  url?: string | null
  source?: string | null
  vendor?: string | null
  publishedAt?: string | null
  sentimentScore?: number
  sentimentLabel?: string
  sentiment?: {
    score: number
    label: string
    confidence?: number
    model?: string
  }
  impactSummary?: string | null
  actionableInsight?: string | null
  contentHash?: string
  qualityPrediction?: boolean | null
  qualityConfidence?: number | null
  storyId?: string | null
  isPrimaryArticle?: boolean
  coverageCount?: number
}

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

  // Generate unique key
  const articleKey =
    article.contentHash ||
    article.url ||
    `article-${index}-${article.headline.substring(0, 30)}`

  return (
    <div
      key={articleKey}
      className="rounded-md border border-border bg-surface-muted/30 p-3"
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
            <span className="text-text font-semibold">
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
    </div>
  )
}
