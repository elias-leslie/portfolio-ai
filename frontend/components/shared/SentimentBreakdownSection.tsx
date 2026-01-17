'use client'

import { Badge } from '@/components/ui/badge'
import {
  formatSentimentScore,
  getSentimentBadgeVariant,
} from '@/lib/utils/news-formatting'

interface NewsSentimentDetail {
  score: number | null
  scoreChange: number | null
  positiveCount: number
  neutralCount: number
  negativeCount: number
  articleCount: number
  latest_published_at?: string | null
  modelBreakdown: Record<string, number>
}

interface SentimentBreakdownSectionProps {
  summary: NewsSentimentDetail
  isExpanded: boolean
}

/**
 * Compute the model coverage display information
 */
function getModelCoverageDisplay(modelBreakdown: Record<string, number>): {
  totalCoverage: number
  finbertCoverage: number
  fallbackCoverage: number
} {
  const totalCoverage = Object.values(modelBreakdown || {}).reduce(
    (sum, val) => sum + val,
    0,
  )
  const finbertCoverage = modelBreakdown?.finbert ?? 0
  const fallbackCoverage = Math.max(totalCoverage - finbertCoverage, 0)
  return { totalCoverage, finbertCoverage, fallbackCoverage }
}

/**
 * Sentiment breakdown section showing score, headline mix, and model coverage.
 * Used in UnifiedNewsIntelligenceCard.
 */
export function SentimentBreakdownSection({
  summary,
  isExpanded,
}: SentimentBreakdownSectionProps) {
  const { totalCoverage, finbertCoverage, fallbackCoverage } =
    getModelCoverageDisplay(summary.modelBreakdown)

  return (
    <div
      className={`flex flex-wrap items-start justify-between gap-4 px-6 py-3 ${isExpanded ? 'border-b border-border' : ''}`}
    >
      <div>
        <p className="text-xs uppercase tracking-wide text-text-muted">
          Sentiment Score
        </p>
        <div className="mt-1 flex items-center gap-2">
          <Badge variant={getSentimentBadgeVariant(summary.score)}>
            {formatSentimentScore(summary.score)}
          </Badge>
          {summary.scoreChange !== null &&
            summary.scoreChange !== undefined && (
              <span
                className={`inline-flex items-center text-xs font-medium ${
                  summary.scoreChange >= 0 ? 'text-gain' : 'text-loss'
                }`}
              >
                {summary.scoreChange >= 0 ? '▲' : '▼'}
                {Math.abs(summary.scoreChange).toFixed(2)}
              </span>
            )}
        </div>
      </div>
      <div className="flex flex-wrap gap-6 text-xs text-text-muted">
        <div>
          <p className="font-semibold text-text">Headline Mix</p>
          <p>
            Positive:{' '}
            <span className="font-medium text-gain">
              {summary.positiveCount}
            </span>
          </p>
          <p>
            Neutral:{' '}
            <span className="font-medium text-text">
              {summary.neutralCount}
            </span>
          </p>
          <p>
            Negative:{' '}
            <span className="font-medium text-loss">
              {summary.negativeCount}
            </span>
          </p>
        </div>
        <div>
          <p className="font-semibold text-text">Model Coverage</p>
          {totalCoverage === 0 ? (
            <p>No articles scored</p>
          ) : finbertCoverage === totalCoverage ? (
            <p>FinBERT coverage</p>
          ) : finbertCoverage === 0 ? (
            <p>Fallback sentiment (VADER)</p>
          ) : (
            <>
              <p>
                FinBERT {finbertCoverage}/{totalCoverage}
              </p>
              {fallbackCoverage > 0 && (
                <p className="text-xs text-text-muted">
                  {fallbackCoverage} fallback
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
