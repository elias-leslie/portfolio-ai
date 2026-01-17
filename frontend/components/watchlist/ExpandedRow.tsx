'use client'

/**
 * Expanded row display for watchlist items
 *
 * This is the main container that assembles all watchlist detail components:
 * - Refresh status indicator
 * - Narrative intelligence (trading signals, action plans)
 * - News intelligence card
 * - Score breakdown (Price + Technical)
 * - Notes editing
 *
 * Refactored from 1,142-line monolithic component into focused subcomponents.
 */

import { UnifiedNewsIntelligenceCard } from '@/components/shared/UnifiedNewsIntelligenceCard'
import type { RefreshStatus, WatchlistItem } from '@/lib/api/watchlist'
import { useNewsIntelligence } from '@/lib/hooks/useNews'
import { usePreferences } from '@/lib/hooks/usePreferences'
import { ExpandedRowNarrative } from './ExpandedRowNarrative'
import { ExpandedRowNotes } from './ExpandedRowNotes'
import { ExpandedRowRefreshStatus } from './ExpandedRowRefreshStatus'
import { ExpandedRowScoreBreakdown } from './ExpandedRowScoreBreakdown'
import { ThesisSection } from './ThesisSection'

interface ExpandedRowProps {
  item: WatchlistItem
  refreshStatus?: RefreshStatus
}

export function ExpandedRow({ item, refreshStatus }: ExpandedRowProps) {
  const { data: preferences } = usePreferences()
  const { data: fullNewsData } = useNewsIntelligence(item.symbol, { limit: 50 })

  const userTimezone = preferences?.displayTimezone ?? 'America/New_York'
  const newsHidden = preferences?.watchlistShowNews === false

  return (
    <div className="space-y-4">
      {/* Refresh Progress */}
      {refreshStatus && (
        <ExpandedRowRefreshStatus
          refreshStatus={refreshStatus}
          symbol={item.symbol}
        />
      )}

      {/* Narrative Intelligence */}
      <ExpandedRowNarrative item={item} />

      {/* Score Breakdown */}
      <ExpandedRowScoreBreakdown item={item} userTimezone={userTimezone} />

      {/* Investment Thesis */}
      <ThesisSection symbol={item.symbol} userTimezone={userTimezone} />

      {/* News Intelligence */}
      <UnifiedNewsIntelligenceCard
        symbol={item.symbol}
        marketNewsData={fullNewsData ?? undefined}
        newsHidden={newsHidden}
        showSentimentBreakdown
        title="News & Sentiment"
        defaultCollapsed
      />

      {/* Notes */}
      <ExpandedRowNotes item={item} />
    </div>
  )
}
