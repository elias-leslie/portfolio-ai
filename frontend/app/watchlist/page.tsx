'use client'

import { PlusCircle, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { AddSymbolModal } from '@/components/watchlist/AddSymbolModal'
import { useWatchlistFilters } from '@/components/watchlist/useWatchlistFilters'
import { WatchlistFilterBar } from '@/components/watchlist/WatchlistFilterBar'
import { WatchlistSearchBar } from '@/components/watchlist/WatchlistSearchBar'
import {
  WatchlistErrorView,
  WatchlistLoadingSkeleton,
} from '@/components/watchlist/WatchlistStateViews'
import { WatchlistTable } from '@/components/watchlist/WatchlistTable'
import { useRefreshWatchlist, useWatchlist } from '@/lib/hooks/useWatchlist'

export default function WatchlistPage() {
  const [addSymbolOpen, setAddSymbolOpen] = useState(false)

  const { data: watchlistData, isLoading, error } = useWatchlist()
  const refreshMutation = useRefreshWatchlist()

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

  const totalCount = watchlistData?.items.length ?? 0
  const description = searchQuery.trim()
    ? `Found ${filteredItems.length} ${filteredItems.length === 1 ? 'symbol' : 'symbols'} matching "${searchQuery}"`
    : styleFilter === 'all'
      ? `Showing all ${totalCount} symbols`
      : `Showing ${filteredItems.length} ${styleFilter} ${filteredItems.length === 1 ? 'play' : 'plays'}`

  return (
    <PageContainer className="py-10">
      <PageHeader
        title="Watchlist"
        description={description}
        size="md"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={handleRefresh}
              disabled={refreshMutation.isPending}
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${refreshMutation.isPending ? 'animate-spin' : ''}`}
              />
              Refresh
            </Button>
            <Button onClick={() => setAddSymbolOpen(true)}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Add Symbol
            </Button>
          </div>
        }
      />

      <WatchlistFilterBar
        totalCount={totalCount}
        signalFilter={signalFilter}
        onSignalChange={setSignalFilter}
        styleFilter={styleFilter}
        onStyleChange={setStyleFilter}
        riskFilter={riskFilter}
        onRiskChange={setRiskFilter}
        counts={counts}
      />

      <WatchlistSearchBar value={searchQuery} onChange={setSearchQuery} />

      {error && <WatchlistErrorView message={error.message} />}
      {isLoading && <WatchlistLoadingSkeleton />}
      {!isLoading && !error && <WatchlistTable items={filteredItems} />}

      <AddSymbolModal
        open={addSymbolOpen}
        onOpenChange={setAddSymbolOpen}
        currentCount={totalCount}
      />
    </PageContainer>
  )
}
