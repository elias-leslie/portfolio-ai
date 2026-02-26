'use client'

import { ArrowUpDown, ChevronDown, Newspaper } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { CardHeader, CardTitle } from '@/components/ui/card'
import type { NewsArticle, NewsSentimentDetail, SortOption } from './types'

interface NewsCardHeaderProps {
  cardTitle: string
  isMarketNews: boolean
  isExpanded: boolean
  onToggleExpanded: () => void
  sortBy: SortOption
  onSortChange: (v: SortOption) => void
  summary: NewsSentimentDetail | null
  articles: NewsArticle[]
}

export function NewsCardHeader({
  cardTitle,
  isMarketNews,
  isExpanded,
  onToggleExpanded,
  sortBy,
  onSortChange,
  summary,
  articles,
}: NewsCardHeaderProps) {
  return (
    <CardHeader
      className={
        isMarketNews
          ? 'p-0 pb-4'
          : 'pb-3 flex flex-row items-center justify-between space-y-0'
      }
    >
      <div className="flex items-center justify-between w-full">
        <button
          type="button"
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
          onClick={onToggleExpanded}
        >
          {isMarketNews && <Newspaper className="h-5 w-5 text-accent" />}
          <CardTitle
            className={
              isMarketNews
                ? 'text-lg font-semibold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent'
                : 'text-base'
            }
          >
            {cardTitle}
          </CardTitle>
          <ChevronDown
            className={`h-4 w-4 text-text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          />
          {!isExpanded && summary && (
            <Badge variant="outline" className="ml-2 text-xs">
              {articles.length} articles
            </Badge>
          )}
        </button>
        {isExpanded && (
          <div className="flex items-center gap-2">
            <ArrowUpDown className="h-3 w-3 text-text-muted" />
            <select
              value={sortBy}
              onChange={(e) => onSortChange(e.target.value as SortOption)}
              className="text-xs border border-border rounded px-2 py-1 bg-surface text-text focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="recent">Recent</option>
              <option value="positive">Most Positive</option>
              <option value="negative">Most Negative</option>
            </select>
          </div>
        )}
      </div>
    </CardHeader>
  )
}
