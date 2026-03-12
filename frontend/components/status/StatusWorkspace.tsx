'use client'

import { AlertCircle, Loader2, RefreshCw } from 'lucide-react'
import { useMemo } from 'react'
import type { NewsHealthResponse } from '@/lib/api/news'
import { useDetailedHealth } from '@/lib/hooks/useHealth'
import { useMarketStatus } from '@/lib/hooks/useMarketIntelligence'
import { useNewsHealth } from '@/lib/hooks/useNewsHealth'
import { formatRelativeTime } from '@/lib/utils'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import {
  SummaryStat,
  SystemChecksPanel,
  ServicePulsePanel,
  SourceHealthPanel,
  NewsVendorsPanel,
  QuotaCoveragePanel,
  RecentRemediationsPanel,
  StaleMaintenancePanel,
  MarketTimingPanel,
} from './StatusPanels'
import { formatInteger, formatPercent, formatHours, marketLabel } from './statusUtils'

export function StatusWorkspace() {
  const healthQuery = useDetailedHealth()
  const marketQuery = useMarketStatus()
  const newsHealthQuery = useNewsHealth()

  const failedSections = [
    healthQuery.error ? 'system health' : null,
    marketQuery.error ? 'market timing' : null,
    newsHealthQuery.error ? 'news pipeline' : null,
  ].filter((value): value is string => Boolean(value))

  const isLoading =
    (!healthQuery.data && healthQuery.isLoading) ||
    (!marketQuery.data && marketQuery.isLoading) ||
    (!newsHealthQuery.data && newsHealthQuery.isLoading)
  const hasFatalError = failedSections.length === 3
  const hasPartialError = failedSections.length > 0 && !hasFatalError
  const isFetching =
    healthQuery.isFetching || marketQuery.isFetching || newsHealthQuery.isFetching

  const sourceRows = useMemo(
    () =>
      Object.entries(healthQuery.data?.sources ?? {}).sort((a, b) => a[0].localeCompare(b[0])),
    [healthQuery.data?.sources],
  )
  const checkRows = useMemo(
    () =>
      Object.entries(healthQuery.data?.checks ?? {}).sort((a, b) => a[0].localeCompare(b[0])),
    [healthQuery.data?.checks],
  )
  const serviceRows = useMemo(
    () =>
      Object.entries(healthQuery.data?.services ?? {}).sort((a, b) => a[0].localeCompare(b[0])),
    [healthQuery.data?.services],
  )
  const vendorRows = useMemo(
    () =>
      Object.entries(newsHealthQuery.data?.vendors ?? {}).sort((a, b) =>
        a[0].localeCompare(b[0]),
      ) as [string, NewsHealthResponse['vendors'][string]][],
    [newsHealthQuery.data?.vendors],
  )

  const apiQuotas = healthQuery.data?.apiQuotas ?? []
  const configuredQuotaCount = apiQuotas.filter((q) => q.configured).length
  const totalQuotaCount = apiQuotas.length
  const staleMaintenanceCount = healthQuery.data?.staleMaintenanceRuns?.length ?? 0

  const watchlistItemsWithScores = healthQuery.data?.watchlistStats?.itemsWithScores ?? null
  const watchlistTotalItems = healthQuery.data?.watchlistStats?.totalItems ?? null
  const watchlistCoverageDetail =
    watchlistItemsWithScores !== null && watchlistTotalItems !== null
      ? `${formatInteger(watchlistItemsWithScores)} of ${formatInteger(watchlistTotalItems)} symbols scored`
      : healthQuery.data?.watchlistStats?.lastRefresh
        ? `Last refresh ${formatRelativeTime(healthQuery.data.watchlistStats.lastRefresh)}`
        : 'No refresh timestamp yet'

  const cacheStats = healthQuery.data?.cacheStats
  const cacheValue =
    cacheStats?.enabled === false ? 'off' : formatPercent(cacheStats?.hitRate)
  const cacheDetail =
    cacheStats?.enabled === false
      ? 'Cache disabled'
      : `Size ${formatInteger(cacheStats?.size)} / ${formatInteger(cacheStats?.maxSize)} · age ${formatHours(cacheStats?.cacheAgeMinutes != null ? cacheStats.cacheAgeMinutes / 60 : null)}`

  const newsPipelineDetail =
    newsHealthQuery.data?.fallbackHeadlines24H != null
      ? `Fallback rate ${formatPercent(newsHealthQuery.data?.fallbackRate24H)} · ${formatInteger(newsHealthQuery.data?.fallbackHeadlines24H)} fallback headlines`
      : `Fallback rate ${formatPercent(newsHealthQuery.data?.fallbackRate24H)}`

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        eyebrow="Operations"
        title="Status"
        description="Check market hours, system health, data freshness, and news pipeline posture without leaving the app."
        actions={
          <Button
            variant="outline"
            onClick={() => {
              void healthQuery.refetch()
              void marketQuery.refetch()
              void newsHealthQuery.refetch()
            }}
            disabled={isFetching}
            aria-busy={isFetching}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {isLoading ? (
        <SectionCard variant="surface">
          <div className="flex min-h-72 items-center justify-center gap-3 text-sm text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            Collecting live operating signals...
          </div>
        </SectionCard>
      ) : null}

      {!isLoading && hasFatalError ? (
        <SectionCard variant="surface">
          <div className="rounded-2xl border border-loss/30 bg-loss/10 p-5 text-sm text-loss">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" />
              Failed to load the operations snapshot.
            </div>
            <p className="mt-2 text-loss/90">
              Check backend availability and try the refresh action again.
            </p>
          </div>
        </SectionCard>
      ) : null}

      {!isLoading && hasPartialError ? (
        <SectionCard variant="surface">
          <div className="rounded-2xl border border-warning/30 bg-warning/10 p-5 text-sm text-warning-foreground">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" />
              Partial snapshot
            </div>
            <p className="mt-2">
              We could not refresh {failedSections.join(', ')}. The rest of the operating signals
              are still shown below.
            </p>
          </div>
        </SectionCard>
      ) : null}

      {!isLoading && !hasFatalError ? (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <SummaryStat
              label="System"
              value={healthQuery.data?.status ?? 'unknown'}
              detail={
                healthQuery.data?.timestamp
                  ? `Updated ${formatRelativeTime(healthQuery.data.timestamp)}`
                  : 'Update time unavailable'
              }
            />
            <SummaryStat
              label="Market"
              value={marketLabel(marketQuery.data?.status)}
              detail={marketQuery.data?.currentTimeEt ?? 'No market clock available'}
            />
            <SummaryStat
              label="Watchlist"
              value={formatInteger(healthQuery.data?.watchlistStats?.itemsWithScores)}
              detail={watchlistCoverageDetail}
            />
            <SummaryStat
              label="News Pipeline"
              value={formatInteger(newsHealthQuery.data?.headlines24H)}
              detail={newsPipelineDetail}
            />
            <SummaryStat label="Cache" value={cacheValue} detail={cacheDetail} />
            <SummaryStat
              label="Quotas"
              value={`${formatInteger(configuredQuotaCount)}/${formatInteger(totalQuotaCount)}`}
              detail={
                totalQuotaCount > 0
                  ? `${formatInteger(configuredQuotaCount)} provider${configuredQuotaCount === 1 ? '' : 's'} configured`
                  : 'No provider quota telemetry yet'
              }
            />
            <SummaryStat
              label="Maintenance Alerts"
              value={formatInteger(staleMaintenanceCount)}
              detail={
                staleMaintenanceCount > 0
                  ? 'Background maintenance runs need attention'
                  : 'No stale maintenance runs reported'
              }
            />
          </section>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <SystemChecksPanel checkRows={checkRows} />
            <ServicePulsePanel
              serviceRows={serviceRows}
              dataFreshnessStatus={healthQuery.data?.dataFreshnessStatus}
              workflowHealth={healthQuery.data?.workflowHealth}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
            <SourceHealthPanel sourceRows={sourceRows} />
            <NewsVendorsPanel vendorRows={vendorRows} />
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <QuotaCoveragePanel
              apiQuotas={apiQuotas}
              configuredCount={configuredQuotaCount}
              totalCount={totalQuotaCount}
            />
            <RecentRemediationsPanel
              recentRemediations={healthQuery.data?.recentRemediations ?? []}
            />
          </div>

          <StaleMaintenancePanel staleRuns={healthQuery.data?.staleMaintenanceRuns ?? []} />

          <MarketTimingPanel
            marketData={marketQuery.data}
            marketLastRefreshedAt={newsHealthQuery.data?.marketLastRefreshedAt}
          />
        </>
      ) : null}
    </PageContainer>
  )
}
