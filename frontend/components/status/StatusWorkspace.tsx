'use client'

import { AlertCircle, Loader2, RefreshCw } from 'lucide-react'
import { type ReactNode, useMemo } from 'react'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { SectionCard } from '@/components/shared/SectionCard'
import type { WorkspaceTab } from '@/components/shared/WorkspaceTabs'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
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
import { cn } from '@/lib/utils'
import {
  DecisionDataHealthPanel,
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

function decisionDataTone(
  status: string | undefined,
): 'default' | 'positive' | 'warning' | 'negative' {
  switch (status) {
    case 'healthy':
      return 'positive'
    case 'degraded':
      return 'warning'
    case 'critical':
      return 'negative'
    default:
      return 'default'
  }
}

function LoadingSectionPanel({
  title,
  description,
  message,
}: {
  title: string
  description: string
  message: string
}) {
  return (
    <SectionCard variant="surface" title={title} description={description}>
      <div className="flex items-center gap-3 text-sm text-text-muted">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        {message}
      </div>
    </SectionCard>
  )
}

export function StatusWorkspace() {
  const healthQuery = useDetailedHealth()
  const marketQuery = useMarketStatus()
  const newsHealthQuery = useNewsHealth()
  const healthPending = !healthQuery.data && healthQuery.isLoading
  const marketPending = !marketQuery.data && marketQuery.isLoading
  const newsPending = !newsHealthQuery.data && newsHealthQuery.isLoading
  const hasAnyData = Boolean(
    healthQuery.data || marketQuery.data || newsHealthQuery.data,
  )

  const failedSections = [
    healthQuery.error ? 'system health' : null,
    marketQuery.error ? 'market timing' : null,
    newsHealthQuery.error ? 'news pipeline' : null,
  ].filter((value): value is string => Boolean(value))

  const isLoading =
    !hasAnyData && (healthPending || marketPending || newsPending)
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
  const watchlistCoverageDetail: ReactNode =
    watchlistItemsWithScores !== null && watchlistTotalItems !== null ? (
      `${formatInteger(watchlistItemsWithScores)} of ${formatInteger(watchlistTotalItems)} symbols scored`
    ) : healthQuery.data?.watchlistStats?.lastRefresh ? (
      <>
        Last refresh{' '}
        <RelativeTime value={healthQuery.data.watchlistStats.lastRefresh} />
      </>
    ) : (
      'No refresh timestamp yet'
    )

  const cacheStats = healthQuery.data?.cacheStats
  const decisionDataHealth = healthQuery.data?.decisionDataHealth
  const decisionDataIssueCount =
    decisionDataHealth?.domains.filter(
      (domain) => domain.severity !== 'healthy',
    ).length ?? 0
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

  const statusTabs: WorkspaceTab[] = [
    {
      value: 'overview',
      label: 'Overview',
      content: (
        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          {healthPending ? (
            <LoadingSectionPanel
              title="Core Connections"
              description="The services and dependencies this app needs in order to stay trustworthy."
              message="Loading core connection checks..."
            />
          ) : (
            <SystemChecksPanel checkRows={checkRows} />
          )}
          {healthPending ? (
            <LoadingSectionPanel
              title="Service Uptime"
              description="Backend, frontend, and worker processes only."
              message="Loading service uptime..."
            />
          ) : (
            <ServicePulsePanel serviceRows={serviceRows} />
          )}
          {healthPending ? (
            <LoadingSectionPanel
              title="Decision Data Health"
              description="Freshness and coverage for the data behind decisions."
              message="Loading decision-data health..."
            />
          ) : (
            <DecisionDataHealthPanel
              decisionDataHealth={decisionDataHealth}
              dataFreshnessStatus={healthQuery.data?.dataFreshnessStatus}
              workflowHealth={healthQuery.data?.workflowHealth}
            />
          )}
        </div>
      ),
    },
    {
      value: 'sources',
      label: 'Sources',
      content: (
        <div className="space-y-6">
          <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
            {healthPending ? (
              <LoadingSectionPanel
                title="Data Sources"
                description="How the outside feeds behind the app are behaving."
                message="Loading provider health signals..."
              />
            ) : (
              <SourceHealthPanel sourceRows={sourceRows} />
            )}
            {newsPending ? (
              <LoadingSectionPanel
                title="News Sources"
                description="Which news feeds are connected and when they last produced articles."
                message="Loading news-source diagnostics..."
              />
            ) : (
              <NewsVendorsPanel vendorRows={vendorRows} />
            )}
          </div>
          {healthPending ? (
            <LoadingSectionPanel
              title="API Limits"
              description="Which data providers are connected and the limits they advertise."
              message="Loading API quota coverage..."
            />
          ) : (
            <QuotaCoveragePanel
              apiQuotas={apiQuotas}
              configuredCount={configuredQuotaCount}
              totalCount={totalQuotaCount}
            />
          )}
        </div>
      ),
    },
    {
      value: 'automation',
      label: 'Automation',
      badge:
        staleMaintenanceCount > 0 ? String(staleMaintenanceCount) : undefined,
      content: (
        <div className="space-y-6">
          {healthPending ? (
            <LoadingSectionPanel
              title="Recent Auto-fixes"
              description="What the app retried or repaired in the last 24 hours."
              message="Loading recent remediation history..."
            />
          ) : (
            <RecentRemediationsPanel
              recentRemediations={healthQuery.data?.recentRemediations ?? []}
            />
          )}

          {healthPending ? (
            <LoadingSectionPanel
              title="Stuck Background Jobs"
              description="Background jobs that have stayed in a running state longer than expected."
              message="Loading background job review..."
            />
          ) : (
            <StaleMaintenancePanel
              staleRuns={healthQuery.data?.staleMaintenanceRuns ?? []}
            />
          )}
        </div>
      ),
    },
    {
      value: 'calendar',
      label: 'Calendar',
      content:
        marketPending || newsPending ? (
          <LoadingSectionPanel
            title="Market Calendar"
            description="Useful when deciding whether today's prices and alerts should already be moving."
            message="Loading market timing signals..."
          />
        ) : (
          <MarketTimingPanel
            marketData={marketQuery.data}
            newsHealth={newsHealthQuery.data}
          />
        ),
    },
  ]

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
              value={
                healthPending
                  ? 'Loading...'
                  : formatEnumLabel(healthQuery.data?.status, 'Unknown')
              }
              detail={
                healthPending ? (
                  'Loading system health...'
                ) : healthQuery.data?.timestamp ? (
                  <>
                    Updated <RelativeTime value={healthQuery.data.timestamp} />
                  </>
                ) : (
                  'Update time unavailable'
                )
              }
              tone={systemTone(healthQuery.data?.status)}
            />
            <SummaryStat
              label="Market"
              value={
                marketPending
                  ? 'Loading...'
                  : marketLabel(marketQuery.data?.status)
              }
              detail={
                marketPending
                  ? 'Loading market calendar...'
                  : marketQuery.data
                    ? `ET clock ${marketQuery.data.currentTimeEt} · latest close through ${marketQuery.data.lastTradingDay} · expected daily data ${marketQuery.data.expectedDataDate}`
                    : 'No market clock available'
              }
              tone={marketTone(marketQuery.data?.status)}
            />
            <SummaryStat
              label="Watchlist"
              value={
                healthPending
                  ? 'Loading...'
                  : watchlistCoveragePct !== null
                    ? formatPercent(watchlistCoveragePct)
                    : formatInteger(
                        healthQuery.data?.watchlistStats?.itemsWithScores,
                      )
              }
              detail={
                healthPending
                  ? 'Loading watchlist coverage...'
                  : watchlistCoverageDetail
              }
            />
            <SummaryStat
              label="News"
              value={
                newsPending
                  ? 'Loading...'
                  : formatInteger(newsHealthQuery.data?.headlines24H)
              }
              detail={
                newsPending
                  ? 'Loading news pipeline health...'
                  : newsPipelineDetail
              }
              tone={newsTone(newsHealthQuery.data?.status)}
            />
            <SummaryStat
              label="Runtime"
              value={formatHours(
                !healthPending && healthQuery.data?.uptimeSeconds != null
                  ? healthQuery.data.uptimeSeconds / 3600
                  : null,
              )}
              detail={
                healthPending
                  ? 'Loading runtime details...'
                  : healthQuery.data?.version
                    ? `Version ${healthQuery.data.version}`
                    : 'Version unavailable'
              }
            />
            <SummaryStat
              label="Decision Data"
              value={
                healthPending
                  ? 'Loading...'
                  : formatEnumLabel(decisionDataHealth?.status, 'Unknown')
              }
              detail={
                healthPending
                  ? 'Loading decision-data health...'
                  : decisionDataHealth
                    ? decisionDataIssueCount > 0
                      ? `${formatInteger(decisionDataIssueCount)} evidence domain${decisionDataIssueCount === 1 ? '' : 's'} need review`
                      : decisionDataHealth.message
                    : 'Decision-data health unavailable'
              }
              tone={decisionDataTone(decisionDataHealth?.status)}
            />
            <SummaryStat
              label="Cache"
              value={healthPending ? 'Loading...' : cacheValue}
              detail={healthPending ? 'Loading cache metrics...' : cacheDetail}
            />
            <SummaryStat
              label="Data Feeds"
              value={healthPending ? 'Loading...' : dataFeedsValue}
              detail={
                healthPending ? 'Loading provider health...' : dataFeedsDetail
              }
              tone={dataFeedsTone}
            />
            <SummaryStat
              label="Jobs To Review"
              value={
                healthPending
                  ? 'Loading...'
                  : formatInteger(staleMaintenanceCount)
              }
              detail={
                healthPending
                  ? 'Loading background job health...'
                  : staleMaintenanceCount > 0
                    ? 'At least one background job needs attention'
                    : 'No stuck background jobs reported'
              }
              tone={staleMaintenanceCount > 0 ? 'negative' : 'default'}
            />
          </section>

          <WorkspaceTabs
            defaultValue="overview"
            ariaLabel="Status workspace sections"
            tabs={statusTabs}
          />
        </>
      ) : null}
    </PageContainer>
  )
}
