import type { NewsHealthResponse } from '@/lib/api/news'
import type { CheckStatus } from '@/lib/api/health'
import type { MarketStatusResponse } from '@/lib/api/market'
import { formatDateTime } from '@/lib/utils'

export function checkVariant(status: CheckStatus | undefined) {
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

export function marketLabel(status: MarketStatusResponse['status'] | undefined) {
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

export function vendorVariant(vendor: NewsHealthResponse['vendors'][string]) {
  if (!vendor.enabled || !vendor.configured) return 'secondary'
  if (vendor.active) return 'success'
  return vendor.lastErrorAt ? 'warning' : 'secondary'
}

export function getVendorActivityTimestamp(vendor: NewsHealthResponse['vendors'][string]) {
  return vendor.lastSuccessAt ?? vendor.lastArticleAt ?? vendor.lastAttemptAt ?? null
}

export function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(1)}%`
}

export function formatInteger(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString()
}

export function formatHours(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(1)}h`
}

export function formatSeconds(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  if (value >= 3600) return `${(value / 3600).toFixed(1)}h`
  if (value >= 60) return `${Math.round(value / 60)}m`
  return `${Math.round(value)}s`
}

export function formatLabel(value: string) {
  return value
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[-_]+/g, ' ')
    .trim()
}

export function formatServiceName(name: string, serviceName?: string) {
  return formatLabel(serviceName ?? name)
}

export function isServiceActive(service: { active?: boolean; status?: string }) {
  if (typeof service.active === 'boolean') return service.active
  return service.status === 'running'
}

export function getCheckLatencyMs(check: {
  responseTimeMs?: number | null
  latencyMs?: number | null
}) {
  return check.responseTimeMs ?? check.latencyMs ?? null
}

export function getWorkflowCount(
  workflowHealth:
    | { totalWorkflows24h?: number; totalWorkflows24H?: number }
    | null
    | undefined,
) {
  return workflowHealth?.totalWorkflows24h ?? workflowHealth?.totalWorkflows24H ?? null
}

export function remediationPresentation(remediation: {
  status: string
  resolved?: boolean
  resolvedAt?: string | null
}): { badgeLabel: string; badgeVariant: 'success' | 'warning'; detail: string | null } {
  if (remediation.resolved) {
    return {
      badgeLabel: 'resolved',
      badgeVariant: 'success',
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
