'use client'

import { PlusCircle, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { AccountsWithPositionsContent } from '@/components/portfolio/AccountsWithPositions'
import { AddAccountDialog } from '@/components/portfolio/AddAccountDialog'
import { AddPositionDialog } from '@/components/portfolio/AddPositionDialog'
import { InvestingMarketPanel } from '@/components/portfolio/InvestingMarketPanel'
import { InvestingNewsPanel } from '@/components/portfolio/InvestingNewsPanel'
import { InvestingOverviewPanel } from '@/components/portfolio/InvestingOverviewPanel'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import type { WorkspaceTab } from '@/components/shared/WorkspaceTabs'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { Button } from '@/components/ui/button'
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
import {
  useAccounts,
  usePortfolio,
  usePortfolioAnalytics,
} from '@/lib/hooks/usePortfolio'
import { useHouseholdDashboard } from '@/lib/hooks/useHousehold'
import {
  useRefreshStatus,
  useRefreshWatchlist,
  useWatchlist,
} from '@/lib/hooks/useWatchlist'
import { cn } from '@/lib/utils'

export default function PortfolioPage() {
  const {
    data: accounts,
    isLoading: accountsLoading,
    isFetching: accountsFetching,
    error: accountsError,
    refetch: refetchAccounts,
  } = useAccounts()
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio()
  const { data: analytics, isLoading: analyticsLoading } = usePortfolioAnalytics()
  const { data: householdDashboard } = useHouseholdDashboard()
  const {
    data: watchlistData,
    isLoading: watchlistLoading,
    error: watchlistError,
    refetch: refetchWatchlist,
    isFetching: watchlistFetching,
  } = useWatchlist()
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

  const [accountOpen, setAccountOpen] = useState(false)
  const [positionOpen, setPositionOpen] = useState(false)
  const [positionDialogKey, setPositionDialogKey] = useState(0)
  const [defaultAccountId, setDefaultAccountId] = useState('')
  const [addSymbolOpen, setAddSymbolOpen] = useState(false)

  const positionCount = portfolio?.positions.length ?? 0
  const evidenceInvestmentAccounts = (householdDashboard?.accounts ?? []).filter(
    (account) =>
      account.currentValue != null &&
      ['retirement', 'taxable', 'education'].includes(account.assetGroup),
  )

  const openPositionDialog = (nextAccountId?: string) => {
    const id = nextAccountId ?? (accounts?.length === 1 ? accounts[0].id : '')
    setDefaultAccountId(id)
    setPositionDialogKey((current) => current + 1)
    setPositionOpen(true)
  }

  const handleRefresh = () => {
    refreshMutation.mutate(undefined, {
      onSuccess: (data) => {
        if (data.status === 'success') {
          toast.success(
            data.message || `Refreshed ${data.refreshedCount} symbols`,
          )
        } else if (data.status === 'partial_success') {
          const failedSymbols =
            data.failed
              ?.slice(0, 3)
              .map((failed) => failed.symbol)
              .join(', ') || ''
          const moreCount = (data.failedCount || 0) - 3
          const failedMsg =
            moreCount > 0
              ? `${failedSymbols} and ${moreCount} more`
              : failedSymbols
          toast.warning(data.message, {
            description: failedMsg ? `Failed: ${failedMsg}` : undefined,
          })
        }
      },
      onError: (error) => {
        toast.error(`Failed to refresh: ${error.message}`)
      },
    })
  }

  const tabs: WorkspaceTab[] = [
    {
      value: 'market',
      label: 'Market',
      content: <InvestingMarketPanel />,
    },
    {
      value: 'news',
      label: 'News',
      content: (
        <InvestingNewsPanel
          watchlistItems={watchlistData?.items ?? []}
          positions={portfolio?.positions ?? []}
        />
      ),
    },
    {
      value: 'symbols',
      label: 'Symbols',
      badge: totalCount > 0 ? String(totalCount) : undefined,
      content: (
        <div className="space-y-4">
          {watchlistError ? (
            <WatchlistErrorView
              message={watchlistError.message}
              onRetry={() => {
                void refetchWatchlist()
              }}
              isRetrying={watchlistFetching}
            />
          ) : null}

          {watchlistLoading ? <WatchlistLoadingSkeleton /> : null}

          {!watchlistLoading && !watchlistError ? (
            <>
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

              {totalCount === 0 ? (
                <WatchlistEmptyState
                  title="No symbols yet"
                  detail="Add a symbol to start tracking setups, scores, and held names in one investing workspace."
                  primaryAction={{
                    label: 'Add Symbol',
                    onClick: () => setAddSymbolOpen(true),
                  }}
                />
              ) : null}

              {totalCount > 0 && filteredItems.length === 0 ? (
                <WatchlistEmptyState
                  title="No symbols match the current filters"
                  detail="Clear the search or reset the filters to bring your symbol list back into view."
                  primaryAction={{
                    label: 'Show all symbols',
                    onClick: resetFilters,
                  }}
                />
              ) : null}

              {filteredItems.length > 0 ? (
                <WatchlistTable
                  items={filteredItems}
                  refreshStatus={refreshStatus}
                />
              ) : null}
            </>
          ) : null}
        </div>
      ),
    },
    {
      value: 'holdings',
      label: 'Holdings',
      badge: positionCount > 0 ? String(positionCount) : undefined,
      content: (
        <AccountsWithPositionsContent
          accounts={accounts}
          accountsLoading={accountsLoading}
          accountsFetching={accountsFetching}
          accountsError={accountsError}
          evidenceInvestmentAccountsCount={evidenceInvestmentAccounts.length}
          onRetryAccounts={() => {
            void refetchAccounts()
          }}
          onAddAccount={() => setAccountOpen(true)}
          onAddPosition={openPositionDialog}
        />
      ),
    },
  ]

  return (
    <PageContainer className="space-y-6 py-8">
      <PageHeader
        title="Investing"
        description="Your portfolio and the market at a glance."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={handleRefresh}
              disabled={refreshMutation.isPending}
              aria-busy={refreshMutation.isPending}
            >
              <RefreshCw
                className={cn(
                  'mr-2 h-4 w-4',
                  refreshMutation.isPending && 'animate-spin',
                )}
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

      <InvestingOverviewPanel
        portfolio={portfolio}
        analytics={analytics}
        accountsCount={accounts ? accounts.length : null}
        householdPortfolioValue={
          householdDashboard?.portfolioContext?.totalPortfolioValue ?? null
        }
        householdInvestmentAccountsCount={evidenceInvestmentAccounts.length}
        isCoreLoading={accountsLoading || portfolioLoading || analyticsLoading}
      />

      <WorkspaceTabs
        defaultValue="market"
        ariaLabel="Investing workspace sections"
        tabs={tabs}
      />

      <AddAccountDialog open={accountOpen} onOpenChange={setAccountOpen} />

      <AddPositionDialog
        key={positionDialogKey}
        open={positionOpen}
        onOpenChange={setPositionOpen}
        defaultAccountId={defaultAccountId}
      />

      <AddSymbolModal
        open={addSymbolOpen}
        onOpenChange={setAddSymbolOpen}
        currentCount={totalCount}
      />
    </PageContainer>
  )
}
