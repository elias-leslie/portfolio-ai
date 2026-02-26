import { useMemo, useState } from 'react'
import { getSentimentScore } from '@/lib/utils/news-formatting'
import type {
  MarketNewsData,
  NewsArticle,
  NewsSentimentDetail,
  RecentNewsPayload,
  SortOption,
  SymbolNewsIntelligence,
} from './types'

interface UseNewsCardOptions {
  newsIntelligence?: SymbolNewsIntelligence | null
  marketNewsData?: MarketNewsData | null
  recentNews?: RecentNewsPayload | null
  onRequestExpanded?: () => void
  defaultCollapsed?: boolean
}

interface UseNewsCardResult {
  showAll: boolean
  sortBy: SortOption
  setSortBy: (v: SortOption) => void
  isExpanded: boolean
  setIsExpanded: (updater: (prev: boolean) => boolean) => void
  articles: NewsArticle[]
  summary: NewsSentimentDetail | null
  sortedArticles: NewsArticle[]
  displayedArticles: NewsArticle[]
  positiveCount: number
  negativeCount: number
  showToggleButton: boolean
  handleToggleShowAll: () => void
}

const DEFAULT_DISPLAY_COUNT = 6

export function useNewsCard({
  newsIntelligence,
  marketNewsData,
  recentNews,
  onRequestExpanded,
  defaultCollapsed = false,
}: UseNewsCardOptions): UseNewsCardResult {
  const [showAll, setShowAll] = useState(false)
  const [sortBy, setSortBy] = useState<SortOption>('recent')
  const [isExpanded, setIsExpanded] = useState(!defaultCollapsed)

  const articles = useMemo(() => {
    if (newsIntelligence) return newsIntelligence.recentArticles || []
    if (marketNewsData) return marketNewsData.articles || []
    if (recentNews) return recentNews.articles || []
    return []
  }, [newsIntelligence, marketNewsData, recentNews])

  const summary = useMemo(() => {
    return newsIntelligence?.summary ?? marketNewsData?.summary ?? recentNews?.summary ?? null
  }, [newsIntelligence, marketNewsData, recentNews])

  const sortedArticles = useMemo(() => {
    const sorted = [...articles]
    if (sortBy === 'positive') return sorted.sort((a, b) => getSentimentScore(b) - getSentimentScore(a))
    if (sortBy === 'negative') return sorted.sort((a, b) => getSentimentScore(a) - getSentimentScore(b))
    return sorted
  }, [articles, sortBy])

  const { balancedArticles, positiveCount, negativeCount } = useMemo(() => {
    if (sortBy !== 'recent') {
      return { balancedArticles: sortedArticles, positiveCount: 0, negativeCount: 0 }
    }
    const withScores = articles.map((a) => ({ article: a, score: getSentimentScore(a) }))
    const byScore = [...withScores].sort((a, b) => b.score - a.score)
    const positive = byScore.filter((x) => x.score > 0).slice(0, 3)
    const negative = byScore.filter((x) => x.score < 0).slice(-3).reverse()
    return {
      balancedArticles: [...positive, ...negative].map((x) => x.article),
      positiveCount: positive.length,
      negativeCount: negative.length,
    }
  }, [articles, sortedArticles, sortBy])

  const displayedArticles = showAll
    ? sortedArticles
    : balancedArticles.slice(0, DEFAULT_DISPLAY_COUNT)

  const showToggleButton =
    Boolean(onRequestExpanded) || sortedArticles.length > DEFAULT_DISPLAY_COUNT

  const handleToggleShowAll = () => {
    if (!showAll) {
      onRequestExpanded?.()
      setShowAll(true)
      return
    }
    setShowAll(false)
  }

  return {
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
  }
}
