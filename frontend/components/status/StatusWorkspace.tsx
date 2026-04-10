'use client'

import { AlertCircle, Loader2, RefreshCw } from 'lucide-react'
import { useMemo } from 'react'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import type { NewsHealthResponse } from '@/lib/api/news'
import {
  formatEnumLabel,
  formatHours,
  formatInteger,
  formatPercent,
} from '@/lib/formatters'
import { useDetailedHealth } from '@/lib/hooks/useHealth'
import { useMarketStatus } from '@/lib/hooks/useMarketIntelligence'
import { useNewsHealth } from '@/lib/hooks/useNewsHealth'
import { cn, formatRelativeTime } from '@/lib/utils'
import {
  MarketTimingPanel,
  NewsVendorsPanel,
  QuotaCoveragePanel,
  RecentRemediationsPanel,
  ServicePulsePanel,
  SourceHealthPanel,
  StaleMaintenancePanel,
  SummaryStat,
  SystemChecksPanel,
} from './StatusPanels'
import { marketLabel, marketTone, newsTone, systemTone } from './statusUtils'

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
    healthQuery.isFetching ||
    marketQuery.isFetching ||
    newsHealthQuery.isFetching

  const sourceRows = useMemo(
    () =>
      Object.entries(healthQuery.data?.sources ?? {}).sort((a, b) =>
        a[0].localeCompare(b[0]),
      ),
    [healthQuery.data?.sources],
  )
  const checkRows = useMemo(
    () =>
      Object.entries(healthQuery.data?.checks ?? {}).sort((a, b) =>
        a[0].localeCompare(b[0]),
      ),
    [healthQuery.data?.checks],
  )
  const serviceRows = useMemo(
    () =>
      Object.entries(healthQuery.data?.services ?? {}).sort((a, b) =>
        a[0].localeCompare(b[0]),
      ),
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
  const staleMaintenanceCount =
    healthQuery.data?.staleMaintenanceRuns?.length ?? 0
  const healthySourceCount = sourceRows.filter(
    ([, source]) => source.status === 'ok',
  ).length
  const downSourceCount = sourceRows.filter(
    ([, source]) => source.status === 'down',
  ).length
  const degradedSourceCount = sourceRows.filter(
    ([, source]) => source.status === 'degraded',
  ).length
  const impairedSourceCount = downSourceCount + degradedSourceCount
  const sourceCount = sourceRows.length
  const dataFeedsIssueParts = [
    downSourceCount > 0 ? `${formatInteger(downSourceCount)} down` : null,
    degradedSourceCount > 0
      ? `${formatInteger(degradedSourceCount)} degraded`
      : null,
  ].filter((part): part is string => Boolean(part))
  const dataFeedsIssueSuffix =
    dataFeedsIssueParts.length > 0
      ? ` · ${dataFeedsIssueParts.join(' · ')}`
      : ''
  const dataFeedsValue =
    sourceCount > 0
      ? `${formatInteger(healthySourceCount)}/${formatInteger(sourceCount)} healthy`
      : '—'
  const dataFeedsDetail =
    sourceCount === 0
      ? 'No provider health checks yet'
      : impairedSourceCount === 0
        ? 'All checked providers are responding'
        : `${formatInteger(impairedSourceCount)} feed${impairedSourceCount === 1 ? '' : 's'} need${impairedSourceCount === 1 ? 's' : ''} review${dataFeedsIssueSuffix}`
  const dataFeedsTone =
    sourceCount === 0
      ? 'default'
      : healthySourceCount === 0
        ? 'negative'
        : impairedSourceCount > 0
          ? 'warning'
          : 'positive'

  const watchlistItemsWithScores =
    healthQuery.data?.watchlistStats?.itemsWithScores ?? null
  const watchlistTotalItems =
    healthQuery.data?.watchlistStats?.totalItems ?? null
  const watchlistCoveragePct =
    watchlistItemsWithScores !== null &&
    watchlistTotalItems !== null &&
    watchlistTotalItems > 0
      ? (watchlistItemsWithScores / watchlistTotalItems) * 100
      : null
  const watchlistCoverageDetail =
    watchlistItemsWithScores !== null && watchlistTotalItems !== null
      ? `${formatInteger(watchlistItemsWithScores)} of ${formatInteger(watchlistTotalItems)} symbols scored`
      : healthQuery.data?.watchlistStats?.lastRefresh
        ? `Last refresh ${formatRelativeTime(healthQuery.data.watchlistStats.lastRefresh)}`
        : 'No refresh timestamp yet'

  const cacheStats = healthQuery.data?.cacheStats
  const cacheAge = formatHours(
    cacheStats?.cacheAgeMinutes != null
      ? cacheStats.cacheAgeMinutes / 60
      : null,
  )
  const cacheValue =
    cacheStats?.enabled === false
      ? 'off'
      : cacheStats?.hitRate != null
        ? formatPercent(cacheStats.hitRate)
        : cacheStats?.totalCached != null
          ? formatInteger(cacheStats.totalCached)
          : '—'
  const cacheDetail =
    cacheStats?.enabled === false
      ? 'Cache disabled'
      : cacheStats?.size != null && cacheStats?.maxSize != null
        ? `Stored responses ${formatInteger(cacheStats.size)} / ${formatInteger(cacheStats.maxSize)} · age ${cacheAge}`
        : cacheStats?.totalCached != null
          ? `Cached prices ${formatInteger(cacheStats.totalCached)} · age ${cacheAge}`
          : 'Cache details unavailable'

  const newsPipelineDetail =
    newsHealthQuery.data?.message ?? 'News health unavailable'

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        eyebrow="Operations"
        title="Status"
        description="See whether the market is open, the app data is current, and any system issue needs attention."
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
            <RefreshCw
              className={cn('mr-2 h-4 w-4', isFetching && 'animate-spin')}
            />
            Refresh
          </Button>
        }
      />

      {isLoading ? (
        <div className="space-y-6" role="status" aria-live="polite">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 animate-stagger">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="skeleton rounded-2xl h-28" />
            ))}
          </div>
          <div className="flex items-center gap-3 text-sm text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            Collecting live operating signals...
          </div>
        </div>
      ) : null}

      {!isLoading && hasFatalError ? (
        <SectionCard variant="surface">
          <div className="rounded-2xl border border-loss/30 bg-loss/10 p-5 text-sm text-loss">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" />
              Failed to load the operations snapshot.
            </div>
            <p className="mt-2 text-loss/90">
              We could not refresh {failedSections.join(', ')}. Check backend
              availability and try the refresh action again.
            </p>
          </div>
        </SectionCard>
      ) : null}

      {!isLoading && hasPartialError ? (
        <SectionCard variant="surface">
          <div className="rounded-2xl border border-warning/30 bg-warning/10 p-5 text-sm text-warning">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" />
              Partial snapshot
            </div>
            <p className="mt-2">
              We could not refresh {failedSections.join(', ')}. The rest of the
              operating signals are still shown below.
            </p>
          </div>
        </SectionCard>
      ) : null}

      {!isLoading && !hasFatalError ? (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 animate-stagger">
            <SummaryStat
              label="System"
              value={formatEnumLabel(healthQuery.data?.status, 'Unknown')}
              detail={
                healthQuery.data?.timestamp
                  ? `Updated ${formatRelativeTime(healthQuery.data.timestamp)}`
                  : 'Update time unavailable'
              }
              tone={systemTone(healthQuery.data?.status)}
            />
            <SummaryStat
              label="Market"
              value={marketLabel(marketQuery.data?.status)}
              detail={
                marketQuery.data?.currentTimeEt ?? 'No market clock available'
              }
              tone={marketTone(marketQuery.data?.status)}
            />
            <SummaryStat
              label="Watchlist"
              value={
                watchlistCoveragePct !== null
                  ? formatPercent(watchlistCoveragePct)
                  : formatInteger(
                      healthQuery.data?.watchlistStats?.itemsWithScores,
                    )
              }
              detail={watchlistCoverageDetail}
            />
            <SummaryStat
              label="News"
              value={formatInteger(newsHealthQuery.data?.headlines24H)}
              detail={newsPipelineDetail}
              tone={newsTone(newsHealthQuery.data?.status)}
            />
            <SummaryStat
              label="Runtime"
              value={formatHours(
                healthQuery.data?.uptimeSeconds != null
                  ? healthQuery.data.uptimeSeconds / 3600
                  : null,
              )}
              detail={
                healthQuery.data?.version
                  ? `Version ${healthQuery.data.version}`
                  : 'Version unavailable'
              }
            />
            <SummaryStat
              label="Cache"
              value={cacheValue}
              detail={cacheDetail}
            />
            <SummaryStat
              label="Data Feeds"
              value={dataFeedsValue}
              detail={dataFeedsDetail}
              tone={dataFeedsTone}
            />
            <SummaryStat
              label="Jobs To Review"
              value={formatInteger(staleMaintenanceCount)}
              detail={
                staleMaintenanceCount > 0
                  ? 'At least one background job needs attention'
                  : 'No stuck background jobs reported'
              }
              tone={staleMaintenanceCount > 0 ? 'negative' : 'default'}
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

          <StaleMaintenancePanel
            staleRuns={healthQuery.data?.staleMaintenanceRuns ?? []}
          />

          <MarketTimingPanel
            marketData={marketQuery.data}
            newsHealth={newsHealthQuery.data}
          />
        </>
      ) : null}
    </PageContainer>
  )
}
