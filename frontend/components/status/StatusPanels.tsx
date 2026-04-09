'use client'

import type {
  HealthCheckResult,
  HealthServiceStatus,
  SourceHealthCheck,
  ApiQuotaInfo,
  RecentRemediation,
  StaleMaintenanceRun,
  DataFreshnessStatus,
  WorkflowHealthInfo,
} from '@/lib/api/health'
import type { MarketStatusResponse } from '@/lib/api/market'
import type { NewsHealthResponse } from '@/lib/api/news'
import { formatRelativeTime, formatDateTime } from '@/lib/utils'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import {
  formatEnumLabel,
  formatPercent,
  formatInteger,
  formatHours,
  formatSeconds,
} from '@/lib/formatters'
import {
  checkVariant,
  marketLabel,
  vendorVariant,
  getVendorActivityTimestamp,
  formatLabel,
  formatServiceName,
  isServiceActive,
  getCheckLatencyMs,
  getWorkflowCount,
  remediationPresentation,
} from './statusUtils'

type SummaryStatTone = 'default' | 'positive' | 'warning' | 'negative'

const toneBorder: Record<SummaryStatTone, string> = {
  default: 'border-border/40',
  positive: 'border-gain/25 border-l-2 border-l-gain/50',
  warning: 'border-warning/25 border-l-2 border-l-warning/50',
  negative: 'border-loss/25 border-l-2 border-l-loss/50',
}

const toneValue: Record<SummaryStatTone, string> = {
  default: 'text-text group-hover:text-primary/90',
  positive: 'text-gain',
  warning: 'text-warning',
  negative: 'text-loss',
}

export function SummaryStat({
  label,
  value,
  detail,
  tone = 'default',
}: {
  label: string
  value: string
  detail: string
  tone?: SummaryStatTone
}) {
  return (
    <div className={`group rounded-2xl border ${toneBorder[tone]} bg-surface-muted/20 p-5 card-interactive hover:border-border/60 hover:bg-surface-muted/30`}>
      <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">{label}</p>
      <p className={`mt-3 font-display italic text-2xl tabular-nums transition-colors ${toneValue[tone]}`}>{value}</p>
      <p className="mt-2 text-xs leading-relaxed text-text-muted">{detail}</p>
    </div>
  )
}

export function EmptyPanelMessage({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border/50 bg-surface-muted/10 p-4 text-sm text-text-muted">
      {message}
    </div>
  )
}

export function SystemChecksPanel({
  checkRows,
}: {
  checkRows: Array<[string, HealthCheckResult]>
}) {
  return (
    <SectionCard
      variant="surface"
      title="Core Connections"
      description="The services and dependencies this app needs in order to stay trustworthy."
    >
      <div className="grid gap-3">
        {checkRows.length === 0 ? (
          <EmptyPanelMessage message="No core connection checks are available right now." />
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
                    {check.message || 'No extra detail provided'}
                  </p>
                </div>
                <div className="text-sm tabular-nums text-text-muted">
                  {latencyMs === null || latencyMs === undefined ? '—' : `${latencyMs}ms`}
                </div>
              </div>
            )
          })
        )}
      </div>
    </SectionCard>
  )
}

export function ServicePulsePanel({
  serviceRows,
  dataFreshnessStatus,
  workflowHealth,
}: {
  serviceRows: Array<[string, HealthServiceStatus]>
  dataFreshnessStatus: DataFreshnessStatus | undefined
  workflowHealth: WorkflowHealthInfo | null | undefined
}) {
  const completedWorkflowCount =
    (workflowHealth?.successfulWorkflows ?? 0) + (workflowHealth?.failedWorkflows ?? 0)
  const totalWorkflowCount = getWorkflowCount(workflowHealth)

  return (
    <SectionCard
      variant="surface"
      title="App Health"
      description="What is running, whether the data is current, and whether background jobs are keeping up."
    >
      <div className="space-y-4">
        <div className="grid gap-3">
          {serviceRows.length === 0 ? (
            <EmptyPanelMessage message="No app-service status entries are available right now." />
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

        {dataFreshnessStatus ? (
          <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text">Data recency</p>
              <Badge
                variant={
                  dataFreshnessStatus.status === 'success' ? 'success' : 'warning'
                }
              >
                {dataFreshnessStatus.status === 'success'
                  ? 'Current'
                  : 'Needs attention'}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-text-muted">
              Last check {formatRelativeTime(dataFreshnessStatus.lastCheck)}
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {formatInteger(dataFreshnessStatus.fresh)} current,{' '}
              {formatInteger(dataFreshnessStatus.stale)} getting old,{' '}
              {formatInteger(dataFreshnessStatus.critical)} overdue
            </p>
            {dataFreshnessStatus.remediationsTriggered ? (
              <p className="mt-2 text-sm text-text-muted">
                Auto-fixes ran {formatInteger(dataFreshnessStatus.remediationsTriggered)} time
                {dataFreshnessStatus.remediationsTriggered === 1 ? '' : 's'} in the latest check.
              </p>
            ) : null}
            {dataFreshnessStatus.error ? (
              <p className="mt-2 text-sm text-loss">
                Data recency issue: {dataFreshnessStatus.error}
              </p>
            ) : null}
          </div>
        ) : (
          <EmptyPanelMessage message="No data-recency summary is available right now." />
        )}

        {workflowHealth ? (
          <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text">Automation health</p>
              <Badge
                variant={
                  workflowHealth.status === 'healthy'
                    ? 'success'
                    : workflowHealth.status === 'critical'
                      ? 'error'
                      : 'warning'
                }
              >
                {formatEnumLabel(workflowHealth.status, 'Unknown')}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-text-muted">
              {completedWorkflowCount > 0
                ? `${formatPercent(workflowHealth.successRate)} of ${formatInteger(completedWorkflowCount)} completed automation runs finished successfully in the last 24h.`
                : workflowHealth.blockedWorkflows > 0
                  ? `No automation runs finished in the last 24h. ${formatInteger(workflowHealth.blockedWorkflows)} ${workflowHealth.blockedWorkflows === 1 ? 'is' : 'are'} stuck or overdue.`
                  : totalWorkflowCount && totalWorkflowCount > 0
                    ? 'Automation started in the last 24h, but nothing has finished yet.'
                    : 'No automation runs were recorded in the last 24h.'}
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {formatInteger(workflowHealth.failedWorkflows)} failed ·{' '}
              {formatInteger(workflowHealth.blockedWorkflows)} stuck
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {workflowHealth.lastSuccessfulWorkflow
                ? `Last success ${formatRelativeTime(workflowHealth.lastSuccessfulWorkflow)}`
                : 'No successful automation run recorded yet.'}
            </p>
            {workflowHealth.lastSuccessfulType ? (
              <p className="mt-2 text-sm text-text-muted">
                Last successful automation: {formatLabel(workflowHealth.lastSuccessfulType)}
              </p>
            ) : null}
          </div>
        ) : (
          <EmptyPanelMessage message="No automation-health summary is available right now." />
        )}
      </div>
    </SectionCard>
  )
}

export function SourceHealthPanel({
  sourceRows,
}: {
  sourceRows: Array<[string, SourceHealthCheck]>
}) {
  return (
    <SectionCard
      variant="surface"
      title="Data Sources"
      description="How the outside feeds behind the app are behaving."
    >
      <div className="grid gap-3">
        {sourceRows.length === 0 ? (
          <EmptyPanelMessage message="No data-source health signals are available right now." />
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
                <p>Worked: {formatPercent(source.successRate)}</p>
                <p>Response time: {formatInteger(source.avgLatencyMs)}ms</p>
                <p>
                  Last good update:{' '}
                  {source.lastSuccess
                    ? formatRelativeTime(source.lastSuccess)
                    : 'No successful fetch recorded'}
                </p>
              </div>
              {(source.rateLimitHits != null || source.inCooldown) && (
                <div className="mt-2 grid gap-2 text-sm text-text-muted md:grid-cols-2">
                  <p>Rate-limit hits: {formatInteger(source.rateLimitHits)}</p>
                  <p>
                    Pause remaining:{' '}
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
  )
}

export function NewsVendorsPanel({
  vendorRows,
}: {
  vendorRows: Array<[string, NewsHealthResponse['vendors'][string]]>
}) {
  return (
    <SectionCard
      variant="surface"
      title="News Sources"
      description="Which news feeds are connected and whether backup feeds had to help."
    >
      <div className="grid gap-3">
        {vendorRows.length === 0 ? (
          <EmptyPanelMessage message="No news-source diagnostics are available right now." />
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
                <p>Connected: {vendor.configured ? 'Yes' : 'No'}</p>
                <p>Last activity: {formatRelativeTime(getVendorActivityTimestamp(vendor))}</p>
                {vendor.lastSuccessAt ? (
                  <p>Last success: {formatRelativeTime(vendor.lastSuccessAt)}</p>
                ) : null}
                <p>Articles in 24h: {formatInteger(vendor.articlesLast24H)}</p>
                <p>Articles in latest pull: {formatInteger(vendor.articlesLastFetch)}</p>
                <p>
                  Latest issue:{' '}
                  {vendor.lastError ? vendor.lastError : vendor.reason ?? 'No recent error'}
                </p>
                {vendor.notes ? <p>Notes: {vendor.notes}</p> : null}
              </div>
            </div>
          ))
        )}
      </div>
    </SectionCard>
  )
}

export function QuotaCoveragePanel({
  apiQuotas,
  configuredCount,
  totalCount,
}: {
  apiQuotas: ApiQuotaInfo[]
  configuredCount: number
  totalCount: number
}) {
  return (
    <SectionCard
      variant="surface"
      title="API Limits"
      description="Which data providers are connected and the limits they advertise."
    >
      {totalCount > 0 ? (
        <div className="mb-3 rounded-2xl border border-border/40 bg-surface/40 px-4 py-3 text-sm text-text-muted">
          {formatInteger(configuredCount)} of {formatInteger(totalCount)} data provider
          {totalCount === 1 ? '' : 's'} connected
        </div>
      ) : null}
      <div className="grid gap-3">
        {apiQuotas.length === 0 ? (
          <EmptyPanelMessage message="No API-limit data is available right now." />
        ) : (
          apiQuotas.map((quota) => (
            <div
              key={quota.sourceName}
              className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-text">{quota.sourceName}</p>
                <Badge variant={quota.configured ? 'success' : 'secondary'}>
                  {quota.configured ? 'connected' : 'needs key'}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-text-muted">
                Rate limit {quota.rateLimit ?? '—'} · Daily {quota.dailyLimit ?? '—'} · Estimated
                capacity {formatInteger(quota.estimatedCapacity)}
              </p>
            </div>
          ))
        )}
      </div>
    </SectionCard>
  )
}

export function RecentRemediationsPanel({
  recentRemediations,
}: {
  recentRemediations: RecentRemediation[]
}) {
  return (
    <SectionCard
      variant="surface"
      title="Recent Auto-fixes"
      description="What the app retried or repaired in the last 24 hours."
    >
      <div className="grid gap-3">
        {recentRemediations.length === 0 ? (
          <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
            No auto-fixes ran in the last 24 hours.
          </div>
        ) : (
          recentRemediations.map((event) => {
            const presentation = remediationPresentation(event)
            return (
              <div
                key={`${event.tableName}-${event.triggeredAt ?? 'unknown'}`}
                className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text">{event.tableName}</p>
                  <Badge variant={presentation.badgeVariant}>{presentation.badgeLabel}</Badge>
                </div>
                <p className="mt-2 text-sm text-text-muted">
                  Detected {formatDateTime(event.triggeredAt)} · Age{' '}
                  {formatHours(event.ageHours)} / alert threshold {formatHours(event.thresholdHours)}
                </p>
                {event.occurrenceCount && event.occurrenceCount > 1 ? (
                  <p className="mt-2 text-sm text-text-muted">
                    This happened {formatInteger(event.occurrenceCount)} times in the last 24h.
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
  )
}

export function StaleMaintenancePanel({
  staleRuns,
}: {
  staleRuns: StaleMaintenanceRun[]
}) {
  if (staleRuns.length === 0) return null
  return (
    <SectionCard
      variant="surface"
      title="Stuck Background Jobs"
      description="Background jobs that have stayed in a running state longer than expected."
    >
      <div className="grid gap-3">
        {staleRuns.map((run) => (
          <div
            key={`${run.taskName}-${run.startedAt ?? 'unknown'}`}
            className="flex items-center justify-between gap-3 rounded-2xl border border-warning/30 bg-warning/10 p-4"
          >
            <div>
              <p className="text-sm font-semibold text-text">{formatLabel(run.taskName)}</p>
              <p className="mt-1 text-sm text-text-muted">
                Started {formatRelativeTime(run.startedAt)}
                {run.dryRun ? ' (dry run)' : ''}
              </p>
            </div>
            <Badge variant="warning">stuck</Badge>
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

export function MarketTimingPanel({
  marketData,
  marketLastRefreshedAt,
}: {
  marketData: MarketStatusResponse | undefined
  marketLastRefreshedAt: string | null | undefined
}) {
  return (
    <SectionCard
      variant="surface"
      title="Market Calendar"
      description="Useful when deciding whether today's prices and alerts should already be moving."
    >
      {!marketData && !marketLastRefreshedAt ? (
        <EmptyPanelMessage message="Market timing data is unavailable right now." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <SummaryStat
            label="Market Session"
            value={marketLabel(marketData?.status)}
            detail={
              marketData?.isHoliday
                ? marketData.holidayName ?? 'Holiday session'
                : 'Regular session'
            }
          />
          <SummaryStat
            label="Expected Market Date"
            value={marketData?.expectedDataDate ?? '—'}
            detail={`Last trading day ${marketData?.lastTradingDay ?? '—'}`}
          />
          <SummaryStat
            label="Next Trading Day"
            value={marketData?.nextTradingDay ?? '—'}
            detail={
              marketData?.isEarlyClose
                ? marketData.earlyCloseName ?? 'Early close'
                : 'Standard close schedule'
            }
          />
          <SummaryStat
            label="News Feed"
            value={marketLastRefreshedAt ? 'Live' : 'Idle'}
            detail={`Market feed last refreshed ${formatRelativeTime(marketLastRefreshedAt)}`}
          />
        </div>
      )}
    </SectionCard>
  )
}
