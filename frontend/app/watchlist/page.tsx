'use client'

import { PlusCircle, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { AddSymbolModal } from '@/components/watchlist/AddSymbolModal'
import { useWatchlistFilters } from '@/components/watchlist/useWatchlistFilters'
import { WatchlistFilterBar } from '@/components/watchlist/WatchlistFilterBar'
import { WatchlistSearchBar } from '@/components/watchlist/WatchlistSearchBar'
import {
  WatchlistEmptyState,
  WatchlistErrorView,
  WatchlistLoadingSkeleton,
} from '@/components/watchlist/WatchlistStateViews'
import { WatchlistTable } from '@/components/watchlist/WatchlistTable'
import { useRefreshStatus, useRefreshWatchlist, useWatchlist } from '@/lib/hooks/useWatchlist'

export default function WatchlistPage() {
  const [addSymbolOpen, setAddSymbolOpen] = useState(false)

  const { data: watchlistData, isLoading, error, refetch, isFetching } = useWatchlist()
  const refreshMutation = useRefreshWatchlist()
  const totalCount = watchlistData?.items.length ?? 0
  const { data: refreshStatus } = useRefreshStatus(totalCount > 0)

  const {
    styleFilter,
    setStyleFilter,
    signalFilter,
    setSignalFilter,
    riskFilter,
    setRiskFilter,
    searchQuery,
    setSearchQuery,
    filteredItems,
    counts,
    hasActiveFilters,
    resetFilters,
  } = useWatchlistFilters(watchlistData?.items ?? [])

  const handleRefresh = () => {
    refreshMutation.mutate(undefined, {
      onSuccess: (data) => {
        if (data.status === 'success') {
          toast.success(data.message || `Refreshed ${data.refreshedCount} symbols`)
        } else if (data.status === 'partial_success') {
          const failedSymbols =
            data.failed?.slice(0, 3).map((f) => f.symbol).join(', ') || ''
          const moreCount = (data.failedCount || 0) - 3
          const failedMsg =
            moreCount > 0 ? `${failedSymbols} and ${moreCount} more` : failedSymbols
          toast.warning(data.message, {
            description: failedMsg ? `Failed: ${failedMsg}` : undefined,
          })
        }
      },
      onError: (err) => {
        toast.error(`Failed to refresh: ${err.message}`)
      },
    })
  }

  const filterLabels = [
    signalFilter !== 'all' ? signalFilter : null,
    styleFilter !== 'all' ? styleFilter : null,
    riskFilter !== 'all' ? riskFilter : null,
  ].filter((label) => label !== null)

  const description = searchQuery.trim()
    ? `Showing ${filteredItems.length} matches for "${searchQuery}"${filterLabels.length ? ` with ${filterLabels.join(', ')} filters` : ''}.`
    : filterLabels.length > 0
      ? `Showing ${filteredItems.length} of ${totalCount} symbols with ${filterLabels.join(', ')} filters.`
      : `Showing all ${totalCount} symbols.`
  const scoredCount = useMemo(
    () => watchlistData?.items.filter((item) => item.currentScore).length ?? 0,
    [watchlistData?.items]
  )
  const alertCount = useMemo(
    () => watchlistData?.items.filter((item) => item.scoreAlert).length ?? 0,
    [watchlistData?.items]
  )
  const staleCount = useMemo(
    () =>
      watchlistData?.items.filter(
        (item) =>
          item.currentScore?.price.stale ||
          item.currentScore?.technical.stale ||
          item.dataQuality?.overallPct === 0,
      ).length ?? 0,
    [watchlistData?.items]
  )
  const scoreCoveragePct =
    totalCount > 0 ? Math.round((scoredCount / totalCount) * 100) : 0

  return (
    <PageContainer className="watchlist-page space-y-6 py-10">
      <PageHeader
        title="Watchlist"
        description={description}
        size="md"
        actions={totalCount > 0 ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={handleRefresh}
              disabled={refreshMutation.isPending}
              aria-busy={refreshMutation.isPending}
            >
              <RefreshCw
                className={cn('mr-2 h-4 w-4', refreshMutation.isPending && 'animate-spin')}
              />
              Refresh
            </Button>
            <Button onClick={() => setAddSymbolOpen(true)}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Add Symbol
            </Button>
          </div>
        ) : undefined}
      />

      {!isLoading && !error && totalCount > 0 ? (
        <div className="rounded-xl border border-border/30 border-l-primary/50 border-l-2 bg-gradient-to-r from-primary/[0.04] to-surface/40 px-4 py-3 text-sm text-text-muted">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span>{totalCount} symbol{totalCount === 1 ? '' : 's'}</span>
            <span>{scoredCount} scored ({scoreCoveragePct}%)</span>
            <span>{alertCount} flagged</span>
            <span>{staleCount} with stale inputs</span>
            {hasActiveFilters && filteredItems.length !== totalCount ? (
              <span>{filteredItems.length} visible after filters</span>
            ) : null}
            {refreshStatus?.isRefreshing ? (
              <span>
                Refreshing
                {refreshStatus.percentComplete != null
                  ? ` ${Math.round(refreshStatus.percentComplete)}%`
                  : refreshStatus.processedItems !== undefined &&
                      refreshStatus.totalItems !== undefined
                    ? ` ${refreshStatus.processedItems}/${refreshStatus.totalItems}`
                    : ''}
              </span>
            ) : null}
            {refreshStatus?.currentSymbol ? (
              <span>Current symbol {refreshStatus.currentSymbol}</span>
            ) : null}
          </div>
        </div>
      ) : null}

      <WatchlistFilterBar
        totalCount={totalCount}
        signalFilter={signalFilter}
        onSignalChange={setSignalFilter}
        styleFilter={styleFilter}
        onStyleChange={setStyleFilter}
        riskFilter={riskFilter}
        onRiskChange={setRiskFilter}
        counts={counts}
        hasActiveFilters={hasActiveFilters}
        onReset={resetFilters}
      />

      <WatchlistSearchBar
        value={searchQuery}
        onChange={setSearchQuery}
        resultCount={filteredItems.length}
        totalCount={totalCount}
      />

      {error && (
        <WatchlistErrorView
          message={error.message}
          onRetry={() => {
            void refetch()
          }}
          isRetrying={isFetching}
        />
      )}
      {isLoading && <WatchlistLoadingSkeleton />}
      {!isLoading && !error && totalCount === 0 && (
        <WatchlistEmptyState
          title="No symbols yet"
          detail='Add a symbol to start tracking live setups, thesis quality, and refresh status.'
          primaryAction={{
            label: 'Add Symbol',
            onClick: () => setAddSymbolOpen(true),
          }}
        />
      )}
      {!isLoading && !error && totalCount > 0 && filteredItems.length === 0 && (
        <WatchlistEmptyState
          title="No symbols match the current filters"
          detail="Clear the search or reset the filters to bring symbols back into view."
          primaryAction={{
            label: 'Show all symbols',
            onClick: resetFilters,
          }}
        />
      )}
      {!isLoading && !error && filteredItems.length > 0 && (
        <WatchlistTable items={filteredItems} refreshStatus={refreshStatus} />
      )}

      <AddSymbolModal
        open={addSymbolOpen}
        onOpenChange={setAddSymbolOpen}
        currentCount={totalCount}
      />
    </PageContainer>
  )
}
