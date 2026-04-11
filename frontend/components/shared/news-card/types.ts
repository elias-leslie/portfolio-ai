export type SortOption = 'recent' | 'positive' | 'negative'

export interface KeyEvent {
  icon: string
  text: string
  timeAgo: string
  isMaterial: boolean
  event_category?: string | null
  published_at?: string | null
}

export interface NewsArticle {
  symbol?: string
  headline: string
  articleHash?: string | null
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
  eventCategory?: string | null
  marketContextTopic?: string | null
  sourceSignalTier?: string | null
  canonicalHeadline?: string | null
  decisionValueScore?: number | null
  decisionValueLabel?: 'high' | 'medium' | 'low' | null
  decisionValueReason?: string | null
}

export interface NewsSentimentDetail {
  score: number | null
  scoreChange: number | null
  positiveCount: number
  neutralCount: number
  negativeCount: number
  articleCount: number
  latest_published_at?: string | null
  modelBreakdown: Record<string, number>
}

export interface SymbolNewsIntelligence {
  headline: string
  sentimentScore: number
  sentimentLabel: string
  articleCount24H: number
  keyEvents: KeyEvent[]
  recentArticles: NewsArticle[]
  summary?: NewsSentimentDetail | null
}

export interface MarketNewsData {
  articles: NewsArticle[]
  summary?: NewsSentimentDetail | null
}

export interface RecentNewsPayload {
  summary?: NewsSentimentDetail
  articles: NewsArticle[]
}

export interface UnifiedNewsIntelligenceCardProps {
  symbol?: string | null
  newsIntelligence?: SymbolNewsIntelligence | null
  marketNewsData?: MarketNewsData | null
  recentNews?: RecentNewsPayload | null
  showHeader?: boolean
  showSentimentBreakdown?: boolean
  newsHidden?: boolean
  title?: string
  onRequestExpanded?: () => void
  isLoadingMore?: boolean
  defaultCollapsed?: boolean
}
