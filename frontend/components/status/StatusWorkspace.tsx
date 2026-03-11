'use client'

import { AlertCircle, Loader2, RefreshCw } from 'lucide-react'
import { useMemo } from 'react'
import type { NewsHealthResponse } from '@/lib/api/news'
import type { CheckStatus } from '@/lib/api/health'
import type { MarketStatusResponse } from '@/lib/api/market'
import { useDetailedHealth } from '@/lib/hooks/useHealth'
import { useMarketStatus } from '@/lib/hooks/useMarketIntelligence'
import { useNewsHealth } from '@/lib/hooks/useNewsHealth'
import { formatDateTime, formatRelativeTime } from '@/lib/utils'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

function checkVariant(status: CheckStatus | undefined) {
  switch (status) {
    case 'ok':
      return 'success'
    case 'degraded':
      return 'warning'
    case 'down':
      return 'error'
    default:
      return 'secondary'
  }
}

function marketLabel(status: MarketStatusResponse['status'] | undefined) {
  switch (status) {
    case 'open':
      return 'Market Open'
    case 'pre_market':
      return 'Pre-Market'
    case 'after_hours':
      return 'After Hours'
    case 'closed':
      return 'Market Closed'
    default:
      return 'Unknown'
  }
}

function vendorVariant(vendor: NewsHealthResponse['vendors'][string]) {
  if (!vendor.enabled || !vendor.configured) return 'secondary'
  if (vendor.active) return 'success'
  return vendor.lastErrorAt ? 'warning' : 'secondary'
}

function getVendorActivityTimestamp(vendor: NewsHealthResponse['vendors'][string]) {
  return vendor.lastSuccessAt ?? vendor.lastArticleAt ?? vendor.lastAttemptAt ?? null
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(1)}%`
}

function formatInteger(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString()
}

function formatHours(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(1)}h`
}

function formatSeconds(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  if (value >= 3600) return `${(value / 3600).toFixed(1)}h`
  if (value >= 60) return `${Math.round(value / 60)}m`
  return `${Math.round(value)}s`
}

function formatLabel(value: string) {
  return value
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[-_]+/g, ' ')
    .trim()
}

function formatServiceName(name: string, serviceName?: string) {
  return formatLabel(serviceName ?? name)
}

function isServiceActive(service: { active?: boolean; status?: string }) {
  if (typeof service.active === 'boolean') return service.active
  return service.status === 'running'
}

function getCheckLatencyMs(check: { responseTimeMs?: number | null; latencyMs?: number | null }) {
  return check.responseTimeMs ?? check.latencyMs ?? null
}

function getWorkflowCount(
  workflowHealth:
    | {
        totalWorkflows24h?: number
        totalWorkflows24H?: number
      }
    | null
    | undefined,
) {
  return workflowHealth?.totalWorkflows24h ?? workflowHealth?.totalWorkflows24H ?? null
}

function remediationPresentation(
  remediation: {
    status: string
    resolved?: boolean
    resolvedAt?: string | null
  },
): {
  badgeLabel: string
  badgeVariant: 'success' | 'warning'
  detail: string | null
} {
  if (remediation.resolved) {
    return {
      badgeLabel: 'resolved',
      badgeVariant: 'success' as const,
      detail: remediation.resolvedAt
        ? `Resolved in the latest freshness check at ${formatDateTime(remediation.resolvedAt)}.`
        : 'Resolved in the latest freshness check.',
    }
  }

  return {
    badgeLabel: remediation.status,
    badgeVariant: remediation.status === 'success' ? 'success' : 'warning',
    detail: null,
  }
}

function SummaryStat({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail: string
}) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-text">{value}</p>
      <p className="mt-2 text-sm text-text-muted">{detail}</p>
    </div>
  )
}

function EmptyPanelMessage({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border/50 bg-surface-muted/10 p-4 text-sm text-text-muted">
      {message}
    </div>
  )
}

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
  const configuredQuotaCount = (healthQuery.data?.apiQuotas ?? []).filter(
    (quota) => quota.configured,
  ).length
  const totalQuotaCount = (healthQuery.data?.apiQuotas ?? []).length
  const watchlistItemsWithScores = healthQuery.data?.watchlistStats?.itemsWithScores ?? null
  const watchlistTotalItems = healthQuery.data?.watchlistStats?.totalItems ?? null
  const watchlistCoverageDetail =
    watchlistItemsWithScores !== null && watchlistTotalItems !== null
      ? `${formatInteger(watchlistItemsWithScores)} of ${formatInteger(watchlistTotalItems)} symbols scored`
      : healthQuery.data?.watchlistStats?.lastRefresh
        ? `Last refresh ${formatRelativeTime(healthQuery.data.watchlistStats.lastRefresh)}`
        : 'No refresh timestamp yet'

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
            disabled={healthQuery.isFetching || marketQuery.isFetching || newsHealthQuery.isFetching}
            aria-busy={
              healthQuery.isFetching || marketQuery.isFetching || newsHealthQuery.isFetching
            }
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${
                healthQuery.isFetching || marketQuery.isFetching || newsHealthQuery.isFetching
                  ? 'animate-spin'
                  : ''
              }`}
            />
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
              detail={`Updated ${formatRelativeTime(healthQuery.data?.timestamp)}`}
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
              detail={
                newsHealthQuery.data?.fallbackHeadlines24H != null
                  ? `Fallback rate ${formatPercent(newsHealthQuery.data?.fallbackRate24H)} · ${formatInteger(newsHealthQuery.data?.fallbackHeadlines24H)} fallback headlines`
                  : `Fallback rate ${formatPercent(newsHealthQuery.data?.fallbackRate24H)}`
              }
            />
            <SummaryStat
              label="Cache"
              value={
                healthQuery.data?.cacheStats?.enabled === false
                  ? 'off'
                  : formatPercent(healthQuery.data?.cacheStats?.hitRate)
              }
              detail={
                healthQuery.data?.cacheStats?.enabled === false
                  ? 'Cache disabled'
                  : `Size ${formatInteger(healthQuery.data?.cacheStats?.size)} / ${formatInteger(healthQuery.data?.cacheStats?.maxSize)} · age ${formatHours(healthQuery.data?.cacheStats?.cacheAgeMinutes != null ? healthQuery.data.cacheStats.cacheAgeMinutes / 60 : null)}`
              }
            />
          </section>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <SectionCard
              variant="surface"
              title="System Checks"
              description="Backend dependencies and service posture from the detailed health endpoint."
            >
              <div className="grid gap-3">
                {checkRows.length === 0 ? (
                  <EmptyPanelMessage message="No dependency checks are available right now." />
                ) : (
                  checkRows.map(([name, check]) => {
                    const latencyMs = getCheckLatencyMs(check)

                    return (
                      <div
                        key={name}
                        className="flex flex-col gap-3 rounded-2xl border border-border/40 bg-surface-muted/20 p-4 md:flex-row md:items-start md:justify-between"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-semibold capitalize text-text">
                              {formatLabel(name)}
                            </p>
                            <Badge variant={checkVariant(check.status)}>{check.status}</Badge>
                          </div>
                          <p className="mt-2 text-sm text-text-muted">
                            {check.message || 'No additional detail provided'}
                          </p>
                        </div>
                        <div className="text-sm text-text-muted">
                          {latencyMs === null || latencyMs === undefined ? '—' : `${latencyMs}ms`}
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </SectionCard>

            <SectionCard
              variant="surface"
              title="Service Pulse"
              description="Service activity, data freshness, and workflow posture."
            >
              <div className="space-y-4">
                <div className="grid gap-3">
                  {serviceRows.length === 0 ? (
                    <EmptyPanelMessage message="No service status entries are available right now." />
                  ) : (
                    serviceRows.map(([name, service]) => (
                      <div
                        key={name}
                        className="flex items-center justify-between gap-3 rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                      >
                        <div>
                          <p className="text-sm font-semibold capitalize text-text">
                            {formatServiceName(name, service.serviceName)}
                          </p>
                          <p className="mt-1 text-sm text-text-muted">
                            {service.message || service.status || 'No service detail provided'}
                          </p>
                          {service.pid || service.port ? (
                            <p className="mt-2 text-xs text-text-muted">
                              {service.pid ? `PID ${service.pid}` : 'PID unavailable'}
                              {service.pid && service.port ? ' · ' : ''}
                              {service.port ? `Port ${service.port}` : ''}
                            </p>
                          ) : null}
                        </div>
                        <Badge variant={isServiceActive(service) ? 'success' : 'warning'}>
                          {isServiceActive(service) ? 'active' : 'inactive'}
                        </Badge>
                      </div>
                    ))
                  )}
                </div>

                <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-text">Data freshness</p>
                    <Badge
                      variant={
                        healthQuery.data?.dataFreshnessStatus?.status === 'success'
                          ? 'success'
                          : 'warning'
                      }
                    >
                      {healthQuery.data?.dataFreshnessStatus?.status ?? 'unknown'}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">
                    Last check {formatRelativeTime(healthQuery.data?.dataFreshnessStatus?.lastCheck)}
                  </p>
                  <p className="mt-2 text-sm text-text-muted">
                    {formatInteger(healthQuery.data?.dataFreshnessStatus?.fresh)} fresh,{' '}
                    {formatInteger(healthQuery.data?.dataFreshnessStatus?.stale)} stale,{' '}
                    {formatInteger(healthQuery.data?.dataFreshnessStatus?.critical)} critical
                  </p>
                  {healthQuery.data?.dataFreshnessStatus?.remediationsTriggered ? (
                    <p className="mt-2 text-sm text-text-muted">
                      {formatInteger(healthQuery.data?.dataFreshnessStatus?.remediationsTriggered)} remediation
                      {healthQuery.data.dataFreshnessStatus.remediationsTriggered === 1 ? '' : 's'} triggered
                      in the latest pass.
                    </p>
                  ) : null}
                  {healthQuery.data?.dataFreshnessStatus?.error ? (
                    <p className="mt-2 text-sm text-loss">
                      Freshness error: {healthQuery.data.dataFreshnessStatus.error}
                    </p>
                  ) : null}
                </div>

                <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-text">Workflow health</p>
                    <Badge
                      variant={
                        healthQuery.data?.workflowHealth?.status === 'healthy'
                          ? 'success'
                          : healthQuery.data?.workflowHealth?.status === 'critical'
                            ? 'error'
                            : 'warning'
                      }
                    >
                      {healthQuery.data?.workflowHealth?.status ?? 'unknown'}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">
                    {formatPercent(healthQuery.data?.workflowHealth?.successRate)} success rate over{' '}
                    {formatInteger(getWorkflowCount(healthQuery.data?.workflowHealth))} workflows in
                    the last 24h.
                  </p>
                  <p className="mt-2 text-sm text-text-muted">
                    {formatInteger(healthQuery.data?.workflowHealth?.failedWorkflows)} failed ·{' '}
                    {formatInteger(healthQuery.data?.workflowHealth?.blockedWorkflows)} blocked
                  </p>
                  <p className="mt-2 text-sm text-text-muted">
                    Last success{' '}
                    {formatRelativeTime(healthQuery.data?.workflowHealth?.lastSuccessfulWorkflow)}
                  </p>
                  {healthQuery.data?.workflowHealth?.lastSuccessfulType ? (
                    <p className="mt-2 text-sm text-text-muted">
                      Last successful workflow type: {formatLabel(healthQuery.data.workflowHealth.lastSuccessfulType)}
                    </p>
                  ) : null}
                </div>
              </div>
            </SectionCard>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
            <SectionCard
              variant="surface"
              title="Source Health"
              description="How the upstream market and reference sources are behaving."
            >
              <div className="grid gap-3">
                {sourceRows.length === 0 ? (
                  <EmptyPanelMessage message="No source health signals are available right now." />
                ) : (
                  sourceRows.map(([name, source]) => (
                    <div
                      key={name}
                      className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-text">{formatLabel(name)}</p>
                        <Badge variant={checkVariant(source.status)}>{source.status}</Badge>
                      </div>
                      <div className="mt-3 grid gap-2 text-sm text-text-muted md:grid-cols-3">
                        <p>Success rate: {formatPercent(source.successRate)}</p>
                        <p>Latency: {formatInteger(source.avgLatencyMs)}ms</p>
                        <p>Last success: {formatRelativeTime(source.lastSuccess)}</p>
                      </div>
                      {(source.rateLimitHits != null || source.inCooldown) && (
                        <div className="mt-2 grid gap-2 text-sm text-text-muted md:grid-cols-2">
                          <p>Rate limit hits: {formatInteger(source.rateLimitHits)}</p>
                          <p>
                            Cooldown:{' '}
                            {source.inCooldown
                              ? formatSeconds(source.cooldownRemainingSeconds)
                              : 'clear'}
                          </p>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </SectionCard>

            <SectionCard
              variant="surface"
              title="News Vendors"
              description="Configuration, freshness, and fallback posture for the current news stack."
            >
              <div className="grid gap-3">
                {vendorRows.length === 0 ? (
                  <EmptyPanelMessage message="No news vendor diagnostics are available right now." />
                ) : (
                  vendorRows.map(([name, vendor]) => (
                    <div
                      key={name}
                      className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold uppercase tracking-wide text-text">
                          {formatLabel(name)}
                        </p>
                        <Badge variant={vendorVariant(vendor)}>
                          {vendor.active ? 'active' : vendor.enabled ? 'idle' : 'disabled'}
                        </Badge>
                      </div>
                      <div className="mt-3 grid gap-2 text-sm text-text-muted">
                        <p>Configured: {vendor.configured ? 'Yes' : 'No'}</p>
                        <p>Last activity: {formatRelativeTime(getVendorActivityTimestamp(vendor))}</p>
                        {vendor.lastSuccessAt ? (
                          <p>Last success: {formatRelativeTime(vendor.lastSuccessAt)}</p>
                        ) : null}
                        <p>Articles 24h: {formatInteger(vendor.articlesLast24H)}</p>
                        <p>Articles last fetch: {formatInteger(vendor.articlesLastFetch)}</p>
                        <p>
                          Last error:{' '}
                          {vendor.lastError ? vendor.lastError : vendor.reason ?? 'No recent error'}
                        </p>
                        {vendor.notes ? <p>Notes: {vendor.notes}</p> : null}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </SectionCard>
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <SectionCard
              variant="surface"
              title="Quota Coverage"
              description="Configured providers and their expected request ceilings."
            >
              <div className="mb-3 rounded-2xl border border-border/40 bg-surface/40 px-4 py-3 text-sm text-text-muted">
                {formatInteger(configuredQuotaCount)} of {formatInteger(totalQuotaCount)} provider
                {totalQuotaCount === 1 ? '' : 's'} configured
              </div>
              <div className="grid gap-3">
                {(healthQuery.data?.apiQuotas ?? []).length === 0 ? (
                  <EmptyPanelMessage message="No API quota configuration is available right now." />
                ) : (
                  (healthQuery.data?.apiQuotas ?? []).map((quota) => (
                    <div
                      key={quota.sourceName}
                      className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-text">{quota.sourceName}</p>
                        <Badge variant={quota.configured ? 'success' : 'secondary'}>
                          {quota.configured ? 'configured' : 'missing key'}
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm text-text-muted">
                        Rate limit {quota.rateLimit ?? '—'} · Daily {quota.dailyLimit ?? '—'} ·
                        Capacity {formatInteger(quota.estimatedCapacity)}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </SectionCard>

            <SectionCard
              variant="surface"
              title="Recent Remediations"
              description="Auto-remediation history from the last 24 hours."
            >
              <div className="grid gap-3">
                {(healthQuery.data?.recentRemediations ?? []).length === 0 ? (
                  <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
                    No remediation actions were recorded in the last 24 hours.
                  </div>
                ) : (
                  healthQuery.data?.recentRemediations.map((event) => {
                    const presentation = remediationPresentation(event)

                    return (
                      <div
                        key={`${event.tableName}-${event.triggeredAt ?? 'unknown'}`}
                        className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-text">{event.tableName}</p>
                          <Badge variant={presentation.badgeVariant}>
                            {presentation.badgeLabel}
                          </Badge>
                        </div>
                        <p className="mt-2 text-sm text-text-muted">
                          Triggered {formatDateTime(event.triggeredAt)} · Age{' '}
                          {formatHours(event.ageHours)} / threshold {formatHours(event.thresholdHours)}
                        </p>
                        {event.occurrenceCount && event.occurrenceCount > 1 ? (
                          <p className="mt-2 text-sm text-text-muted">
                            Repeated {formatInteger(event.occurrenceCount)} times in the last 24h.
                          </p>
                        ) : null}
                        {presentation.detail ? (
                          <p className="mt-2 text-sm text-text-muted">{presentation.detail}</p>
                        ) : null}
                        <p className="mt-2 text-sm text-text-muted">
                          {event.reason ?? event.errorMessage ?? 'No additional detail'}
                        </p>
                      </div>
                    )
                  })
                )}
              </div>
            </SectionCard>
          </div>

          <SectionCard
            variant="surface"
            title="Market Timing"
            description="Useful when stale data warnings show up or when deciding whether today’s signals are actionable."
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <SummaryStat
                label="Current Session"
                value={marketLabel(marketQuery.data?.status)}
                detail={
                  marketQuery.data?.isHoliday
                    ? marketQuery.data.holidayName ?? 'Holiday session'
                    : 'Regular session'
                }
              />
              <SummaryStat
                label="Expected Data Date"
                value={marketQuery.data?.expectedDataDate ?? '—'}
                detail={`Last trading day ${marketQuery.data?.lastTradingDay ?? '—'}`}
              />
              <SummaryStat
                label="Next Trading Day"
                value={marketQuery.data?.nextTradingDay ?? '—'}
                detail={
                  marketQuery.data?.isEarlyClose
                    ? marketQuery.data.earlyCloseName ?? 'Early close'
                    : 'Standard close schedule'
                }
              />
              <SummaryStat
                label="News Refresh"
                value={newsHealthQuery.data?.marketLastRefreshedAt ? 'live' : 'idle'}
                detail={`Market feed last refreshed ${formatRelativeTime(newsHealthQuery.data?.marketLastRefreshedAt)}`}
              />
            </div>
          </SectionCard>
        </>
      ) : null}
    </PageContainer>
  )
}
