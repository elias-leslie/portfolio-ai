'use client'

export const dynamic = 'force-dynamic'

import { PlusCircle, RefreshCw } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { toast } from 'sonner'
import { PriorRunsSidebar } from '@/components/committee/PriorRunsSidebar'
import { AccountsWithPositionsContent } from '@/components/portfolio/AccountsWithPositions'
import { AddAccountDialog } from '@/components/portfolio/AddAccountDialog'
import { AddPositionDialog } from '@/components/portfolio/AddPositionDialog'
import { InvestingNewsPanel } from '@/components/portfolio/InvestingNewsPanel'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import type { WorkspaceTab } from '@/components/shared/WorkspaceTabs'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { SignalsTabContent } from '@/components/signals/SignalsTabContent'
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
import { startCommitteeRun } from '@/lib/committee/api'
import { useAccounts, usePortfolio } from '@/lib/hooks/usePortfolio'
import { useBlendedSignals } from '@/lib/hooks/useSignals'
import {
  useRefreshStatus,
  useRefreshWatchlist,
  useWatchlist,
} from '@/lib/hooks/useWatchlist'
import { cn } from '@/lib/utils'

function CommitteeTabContent() {
  const router = useRouter()
  const [symbol, setSymbol] = useState('')
  const [starting, setStarting] = useState(false)

  const handleStart = async (event: React.FormEvent) => {
    event.preventDefault()
    const cleaned = symbol.trim().toUpperCase()
    if (!cleaned) return
    setStarting(true)
    try {
      const result = await startCommitteeRun({ symbol: cleaned })
      toast.success(`Committee run started for ${cleaned}`)
      router.push(`/portfolio/committee/${result.run_id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start run')
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
      <div className="overflow-hidden rounded-2xl border border-border bg-gradient-to-b from-surface to-bg">
        <div className="flex items-center justify-between border-b border-border-subtle px-4 py-2.5 text-[10px] uppercase tracking-[0.18em] text-text-muted/70">
          <span>Start a run</span>
          <span className="font-mono text-text-muted">
            in-process · pause / resume / abort
          </span>
        </div>
        <form
          onSubmit={handleStart}
          className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center"
        >
          <input
            type="text"
            placeholder="Symbol (e.g. NVDA)"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="flex-1 rounded-xl border border-border-subtle bg-surface px-3 py-2 text-sm uppercase tracking-[0.16em] text-text placeholder:text-text-muted/60 focus:outline-none focus:ring-1 focus:ring-primary/40"
            maxLength={12}
          />
          <Button type="submit" disabled={starting || !symbol.trim()}>
            {starting ? 'Starting…' : 'Start Committee'}
          </Button>
        </form>
        <p className="px-4 pb-4 text-xs text-text-muted/80">
          Multi-agent decision: four analysts, bull/bear debate, IPS checks,
          risk vote, PM verdict. Approve to execute a paper trade. Each run runs
          in-process — no cron, no background tokens.
        </p>
      </div>
      <PriorRunsSidebar />
    </div>
  )
}

function PortfolioPageContent() {
  const {
    data: accounts,
    isLoading: accountsLoading,
    isFetching: accountsFetching,
    error: accountsError,
    refetch: refetchAccounts,
  } = useAccounts()
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio()
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
  const { data: blendedSignals } = useBlendedSignals({ limit: 100 })

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
      value: 'news',
      label: 'News',
      content: (
        <InvestingNewsPanel
          watchlistItems={watchlistData?.items ?? []}
          positions={portfolio?.positions ?? []}
          isInputLoading={portfolioLoading || watchlistLoading}
        />
      ),
    },
    {
      value: 'signals',
      label: 'Signals',
      badge: blendedSignals?.rows.length
        ? String(blendedSignals.rows.length)
        : undefined,
      content: <SignalsTabContent />,
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
          onRetryAccounts={() => {
            void refetchAccounts()
          }}
          onAddAccount={() => setAccountOpen(true)}
          onAddPosition={openPositionDialog}
        />
      ),
    },
    {
      value: 'committee',
      label: 'Committee',
      content: <CommitteeTabContent />,
    },
  ]

  return (
    <PageContainer className="space-y-6 py-8">
      <PageHeader
        title="Investing"
        description="Market, news, symbols, and holdings."
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

      <WorkspaceTabs
        defaultValue="symbols"
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

export default function PortfolioPage() {
  return <PortfolioPageContent />
}
