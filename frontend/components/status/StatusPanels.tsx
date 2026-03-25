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
  positive: 'border-gain/25',
  warning: 'border-warning/25',
  negative: 'border-loss/25',
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
  return (
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

        {dataFreshnessStatus ? (
          <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text">Data freshness</p>
              <Badge
                variant={
                  dataFreshnessStatus.status === 'success' ? 'success' : 'warning'
                }
              >
                {dataFreshnessStatus.status}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-text-muted">
              Last check {formatRelativeTime(dataFreshnessStatus.lastCheck)}
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {formatInteger(dataFreshnessStatus.fresh)} fresh,{' '}
              {formatInteger(dataFreshnessStatus.stale)} stale,{' '}
              {formatInteger(dataFreshnessStatus.critical)} critical
            </p>
            {dataFreshnessStatus.remediationsTriggered ? (
              <p className="mt-2 text-sm text-text-muted">
                {formatInteger(dataFreshnessStatus.remediationsTriggered)} remediation
                {dataFreshnessStatus.remediationsTriggered === 1 ? '' : 's'} triggered in the latest
                pass.
              </p>
            ) : null}
            {dataFreshnessStatus.error ? (
              <p className="mt-2 text-sm text-loss">
                Freshness error: {dataFreshnessStatus.error}
              </p>
            ) : null}
          </div>
        ) : (
          <EmptyPanelMessage message="No data freshness summary is available right now." />
        )}

        {workflowHealth ? (
          <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text">Workflow health</p>
              <Badge
                variant={
                  workflowHealth.status === 'healthy'
                    ? 'success'
                    : workflowHealth.status === 'critical'
                      ? 'error'
                      : 'warning'
                }
              >
                {workflowHealth.status}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-text-muted">
              {formatPercent(workflowHealth.successRate)} success rate over{' '}
              {formatInteger(getWorkflowCount(workflowHealth))} workflows in the last 24h.
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {formatInteger(workflowHealth.failedWorkflows)} failed ·{' '}
              {formatInteger(workflowHealth.blockedWorkflows)} blocked
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {workflowHealth.lastSuccessfulWorkflow
                ? `Last success ${formatRelativeTime(workflowHealth.lastSuccessfulWorkflow)}`
                : 'No successful workflow recorded yet.'}
            </p>
            {workflowHealth.lastSuccessfulType ? (
              <p className="mt-2 text-sm text-text-muted">
                Last successful workflow type: {formatLabel(workflowHealth.lastSuccessfulType)}
              </p>
            ) : null}
          </div>
        ) : (
          <EmptyPanelMessage message="No workflow health summary is available right now." />
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
                <p>
                  Last success:{' '}
                  {source.lastSuccess
                    ? formatRelativeTime(source.lastSuccess)
                    : 'No successful fetch recorded'}
                </p>
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
      title="Quota Coverage"
      description="Configured providers and their expected request ceilings."
    >
      {totalCount > 0 ? (
        <div className="mb-3 rounded-2xl border border-border/40 bg-surface/40 px-4 py-3 text-sm text-text-muted">
          {formatInteger(configuredCount)} of {formatInteger(totalCount)} provider
          {totalCount === 1 ? '' : 's'} configured
        </div>
      ) : null}
      <div className="grid gap-3">
        {apiQuotas.length === 0 ? (
          <EmptyPanelMessage message="No API quota configuration is available right now." />
        ) : (
          apiQuotas.map((quota) => (
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
                Rate limit {quota.rateLimit ?? '—'} · Daily {quota.dailyLimit ?? '—'} · Capacity{' '}
                {formatInteger(quota.estimatedCapacity)}
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
      title="Recent Remediations"
      description="Auto-remediation history from the last 24 hours."
    >
      <div className="grid gap-3">
        {recentRemediations.length === 0 ? (
          <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
            No remediation actions were recorded in the last 24 hours.
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
      title="Stale Maintenance Runs"
      description="Background tasks stuck in running state past the alert threshold."
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
            <Badge variant="warning">stale</Badge>
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
      title="Market Timing"
      description="Useful when stale data warnings show up or when deciding whether today's signals are actionable."
    >
      {!marketData && !marketLastRefreshedAt ? (
        <EmptyPanelMessage message="Market timing data is unavailable right now." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <SummaryStat
            label="Current Session"
            value={marketLabel(marketData?.status)}
            detail={
              marketData?.isHoliday
                ? marketData.holidayName ?? 'Holiday session'
                : 'Regular session'
            }
          />
          <SummaryStat
            label="Expected Data Date"
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
            label="News Refresh"
            value={marketLastRefreshedAt ? 'live' : 'idle'}
            detail={`Market feed last refreshed ${formatRelativeTime(marketLastRefreshedAt)}`}
          />
        </div>
      )}
    </SectionCard>
  )
}
