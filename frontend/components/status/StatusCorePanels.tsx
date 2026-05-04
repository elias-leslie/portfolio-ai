'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type {
  HealthCheckResult,
  HealthServiceStatus,
  SourceHealthCheck,
} from '@/lib/api/health'
import { formatInteger, formatPercent, formatSeconds } from '@/lib/formatters'
import { formatRelativeTime } from '@/lib/utils'
import { EmptyPanelMessage } from './StatusPanelPrimitives'
import {
  checkVariant,
  formatLabel,
  formatServiceName,
  getCheckLatencyMs,
  isServiceActive,
} from './statusUtils'

function sourceStatePresentation(source: SourceHealthCheck): {
  label: string
  variant: 'success' | 'warning' | 'error' | 'secondary'
} {
  if (source.inCooldown || (source.rateLimitHits ?? 0) > 0) {
    return { label: 'quota-limited', variant: 'warning' }
  }
  if (source.status === 'ok') {
    return { label: 'connected', variant: 'success' }
  }
  if (
    source.statusReason?.toLowerCase().includes('older') ||
    source.statusReason?.toLowerCase().includes('no successful') ||
    !source.lastSuccess
  ) {
    return {
      label: 'stale',
      variant: source.status === 'down' ? 'error' : 'warning',
    }
  }
  return {
    label: source.status,
    variant: checkVariant(source.status),
  }
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
                    <Badge variant={checkVariant(check.status)}>
                      {check.status}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">
                    {check.message || 'No extra detail provided'}
                  </p>
                </div>
                <div className="text-sm tabular-nums text-text-muted">
                  {latencyMs === null || latencyMs === undefined
                    ? '—'
                    : `${latencyMs}ms`}
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
}: {
  serviceRows: Array<[string, HealthServiceStatus]>
}) {
  return (
    <SectionCard
      variant="surface"
      title="Service Uptime"
      description="Backend, frontend, and worker processes only."
    >
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
                  {service.message ||
                    service.status ||
                    'No service detail provided'}
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
          sourceRows.map(([name, source]) => {
            const state = sourceStatePresentation(source)
            return (
              <div
                key={name}
                className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text">
                    {formatLabel(name)}
                  </p>
                  <Badge variant={state.variant}>{state.label}</Badge>
                </div>
                <div className="mt-3 grid gap-2 text-sm text-text-muted md:grid-cols-3">
                  <p>Request success: {formatPercent(source.successRate)}</p>
                  <p>Response time: {formatInteger(source.avgLatencyMs)}ms</p>
                  <p>
                    Last good update:{' '}
                    {source.lastSuccess
                      ? formatRelativeTime(source.lastSuccess)
                      : 'No successful fetch recorded'}
                  </p>
                </div>
                {source.statusReason ? (
                  <p className="mt-2 text-sm text-text-muted">
                    Why: {source.statusReason}
                  </p>
                ) : null}
                {(source.rateLimitHits != null || source.inCooldown) && (
                  <div className="mt-2 grid gap-2 text-sm text-text-muted md:grid-cols-2">
                    <p>
                      Rate-limit hits: {formatInteger(source.rateLimitHits)}
                    </p>
                    <p>
                      Pause remaining:{' '}
                      {source.inCooldown
                        ? formatSeconds(source.cooldownRemainingSeconds)
                        : 'clear'}
                    </p>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </SectionCard>
  )
}
