'use client'

import { PlusCircle, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { AccountsWithPositionsContent } from '@/components/portfolio/AccountsWithPositions'
import { AddAccountDialog } from '@/components/portfolio/AddAccountDialog'
import { AddPositionDialog } from '@/components/portfolio/AddPositionDialog'
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
import { formatCurrency, formatPercent } from '@/lib/formatters'
import {
  useAccounts,
  usePortfolio,
  usePortfolioAnalytics,
} from '@/lib/hooks/usePortfolio'
import {
  useRefreshStatus,
  useRefreshWatchlist,
  useWatchlist,
} from '@/lib/hooks/useWatchlist'
import { cn } from '@/lib/utils'

function MetricCard({
  label,
  value,
  detail,
  tone = 'default',
}: {
  label: string
  value: string
  detail: string
  tone?: 'default' | 'gain' | 'loss'
}) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface/60 px-4 py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
        {label}
      </p>
      <p
        className={cn(
          'mt-2 text-2xl font-semibold tracking-tight',
          tone === 'gain'
            ? 'text-gain'
            : tone === 'loss'
              ? 'text-loss'
              : 'text-text',
        )}
      >
        {value}
      </p>
      <p className="mt-1 text-sm text-text-muted">{detail}</p>
    </div>
  )
}

export default function PortfolioPage() {
  const {
    data: accounts,
    isLoading: accountsLoading,
    isFetching: accountsFetching,
    error: accountsError,
    refetch: refetchAccounts,
  } = useAccounts()
  const { data: portfolio } = usePortfolio()
  const { data: analytics } = usePortfolioAnalytics()
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
  const uniqueHeldSymbols = new Set(
    portfolio?.positions.map((position) => position.symbol.toUpperCase()) ?? [],
  ).size
  const flaggedCount =
    watchlistData?.items.filter((item) => item.scoreAlert).length ?? 0
  const staleCount =
    watchlistData?.items.filter(
      (item) =>
        item.currentScore?.price.stale ||
        item.currentScore?.technical.stale ||
        item.dataQuality?.overallPct === 0,
    ).length ?? 0
  const diversificationLabel = analytics?.diversificationScore
    ? `${analytics.diversificationScore.score}`
    : '—'
  const topHoldingPct = analytics?.concentration?.topHoldingPct ?? null
  const totalGain = portfolio?.totalGain ?? 0

  const metrics = useMemo(
    () => [
      {
        label: 'Portfolio Value',
        value: formatCurrency(portfolio?.totalValue ?? 0),
        detail: `${positionCount} position${positionCount === 1 ? '' : 's'} across ${accounts?.length ?? 0} account${(accounts?.length ?? 0) === 1 ? '' : 's'}.`,
        tone: 'default' as const,
      },
      {
        label: 'Total Gain',
        value: formatCurrency(totalGain),
        detail: formatPercent(portfolio?.totalGainPct ?? 0, {
          decimals: 2,
          sign: true,
        }),
        tone: totalGain >= 0 ? ('gain' as const) : ('loss' as const),
      },
      {
        label: 'Diversification',
        value: diversificationLabel,
        detail:
          topHoldingPct != null
            ? `Top holding ${topHoldingPct.toFixed(1)}% of portfolio.`
            : 'Portfolio concentration unavailable.',
        tone: 'default' as const,
      },
      {
        label: 'Watchlist',
        value: String(totalCount),
        detail: `${uniqueHeldSymbols} held · ${flaggedCount} flagged · ${staleCount} stale.`,
        tone: 'default' as const,
      },
    ],
    [
      accounts?.length,
      diversificationLabel,
      flaggedCount,
      portfolio?.totalGainPct,
      portfolio?.totalValue,
      positionCount,
      staleCount,
      topHoldingPct,
      totalCount,
      totalGain,
      uniqueHeldSymbols,
    ],
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
      value: 'symbols',
      label: 'Symbols',
      badge: totalCount > 0 ? String(totalCount) : undefined,
      content: (
        <div className="space-y-4">
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

          {!watchlistLoading && !watchlistError && totalCount === 0 ? (
            <WatchlistEmptyState
              title="No symbols yet"
              detail="Add a symbol to start tracking setups, scores, and held names in one investing workspace."
              primaryAction={{
                label: 'Add Symbol',
                onClick: () => setAddSymbolOpen(true),
              }}
            />
          ) : null}

          {!watchlistLoading &&
          !watchlistError &&
          totalCount > 0 &&
          filteredItems.length === 0 ? (
            <WatchlistEmptyState
              title="No symbols match the current filters"
              detail="Clear the search or reset the filters to bring your symbol list back into view."
              primaryAction={{
                label: 'Show all symbols',
                onClick: resetFilters,
              }}
            />
          ) : null}

          {!watchlistLoading && !watchlistError && filteredItems.length > 0 ? (
            <WatchlistTable
              items={filteredItems}
              refreshStatus={refreshStatus}
            />
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
  ]

  return (
    <PageContainer className="space-y-6 py-8">
      <PageHeader
        title="Investing"
        description="Start with the health of your portfolio, then open symbols or holdings only when you need the detail."
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

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            detail={metric.detail}
            tone={metric.tone}
          />
        ))}
      </div>

      <InvestingOverviewPanel
        watchlistItems={watchlistData?.items ?? []}
        positions={portfolio?.positions ?? []}
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
