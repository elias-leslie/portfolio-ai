'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type {
  DataFreshnessStatus,
  DecisionDataDomain,
  DecisionDataHealth,
  WorkflowHealthInfo,
} from '@/lib/api/health'
import { formatEnumLabel, formatInteger, formatPercent } from '@/lib/formatters'
import { formatRelativeTime } from '@/lib/utils'
import { EmptyPanelMessage } from './StatusPanelPrimitives'
import { formatLabel, getWorkflowCount } from './statusUtils'

function decisionSeverityVariant(
  severity: DecisionDataDomain['severity'] | undefined,
): 'success' | 'warning' | 'error' | 'secondary' {
  switch (severity) {
    case 'healthy':
      return 'success'
    case 'critical':
      return 'error'
    case 'warning':
      return 'warning'
    default:
      return 'secondary'
  }
}

function decisionHealthVariant(
  status: DecisionDataHealth['status'] | undefined,
): 'success' | 'warning' | 'error' | 'secondary' {
  switch (status) {
    case 'healthy':
      return 'success'
    case 'critical':
      return 'error'
    case 'degraded':
      return 'warning'
    default:
      return 'secondary'
  }
}

function evidenceValue(
  evidence: Record<string, unknown> | undefined,
  ...keys: string[]
) {
  for (const key of keys) {
    if (evidence && key in evidence) return evidence[key]
  }
  return undefined
}

function evidenceNumber(
  evidence: Record<string, unknown> | undefined,
  ...keys: string[]
) {
  const value = evidenceValue(evidence, ...keys)
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function evidenceString(
  evidence: Record<string, unknown> | undefined,
  ...keys: string[]
) {
  const value = evidenceValue(evidence, ...keys)
  return typeof value === 'string' && value.trim() ? value : null
}

function evidenceArrayCount(
  evidence: Record<string, unknown> | undefined,
  ...keys: string[]
) {
  const value = evidenceValue(evidence, ...keys)
  return Array.isArray(value) ? value.length : 0
}

function decisionEvidenceLine(domain: DecisionDataDomain) {
  const evidence = domain.evidence
  switch (domain.key) {
    case 'market_data': {
      return `${formatInteger(evidenceNumber(evidence, 'fresh'))} current, ${formatInteger(evidenceNumber(evidence, 'stale'))} getting old, ${formatInteger(evidenceNumber(evidence, 'critical'))} overdue`
    }
    case 'automation_recency': {
      return `${formatInteger(evidenceNumber(evidence, 'total_workflows_24h', 'totalWorkflows24h'))} runs · ${formatInteger(evidenceNumber(evidence, 'failed_workflows', 'failedWorkflows'))} failed · ${formatInteger(evidenceNumber(evidence, 'blocked_workflows', 'blockedWorkflows'))} stuck`
    }
    case 'source_connectivity': {
      return `${formatInteger(evidenceNumber(evidence, 'connected_sources', 'connectedSources'))} connected · ${formatInteger(evidenceArrayCount(evidence, 'disabled_sources', 'disabledSources'))} disabled · ${formatInteger(evidenceArrayCount(evidence, 'quota_limited_sources', 'quotaLimitedSources'))} quota-limited`
    }
    case 'household_evidence': {
      return `Net worth ${formatEnumLabel(evidenceString(evidence, 'net_worth_status', 'netWorthStatus'), 'unknown')} · Spend ${formatEnumLabel(evidenceString(evidence, 'monthly_spend_status', 'monthlySpendStatus'), 'unknown')}`
    }
    case 'prediction_macro': {
      return `Snapshot ${formatEnumLabel(evidenceString(evidence, 'state'), 'unknown')} · Macro ${formatEnumLabel(evidenceString(evidence, 'macro_freshness', 'macroFreshness'), 'unknown')}`
    }
    default:
      return null
  }
}

export function DecisionDataHealthPanel({
  decisionDataHealth,
  dataFreshnessStatus,
  workflowHealth,
}: {
  decisionDataHealth: DecisionDataHealth | undefined
  dataFreshnessStatus: DataFreshnessStatus | undefined
  workflowHealth: WorkflowHealthInfo | null | undefined
}) {
  const completedWorkflowCount =
    (workflowHealth?.successfulWorkflows ?? 0) +
    (workflowHealth?.failedWorkflows ?? 0)
  const totalWorkflowCount = getWorkflowCount(workflowHealth)
  const displayedHealth =
    decisionDataHealth ??
    (dataFreshnessStatus || workflowHealth
      ? {
          status: 'unknown' as const,
          message: 'Decision-data health contract unavailable.',
          domains: [],
        }
      : undefined)

  return (
    <SectionCard
      variant="surface"
      title="Decision Data Health"
      description="Freshness and coverage for evidence used by forecasts, money views, automation, and data-source decisions."
    >
      {displayedHealth ? (
        <div className="space-y-4">
          <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text">
                Decision-data snapshot
              </p>
              <Badge variant={decisionHealthVariant(displayedHealth.status)}>
                {formatEnumLabel(displayedHealth.status, 'Unknown')}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-text-muted">
              {displayedHealth.message}
            </p>
          </div>
          <div className="grid gap-3">
            {displayedHealth.domains.map((domain) => {
              const evidenceLine = decisionEvidenceLine(domain)
              return (
                <div
                  key={domain.key}
                  className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-text">
                      {domain.label}
                    </p>
                    <Badge variant={decisionSeverityVariant(domain.severity)}>
                      {formatEnumLabel(domain.status, 'Unknown')}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">
                    {domain.message}
                  </p>
                  {domain.lastUpdated ? (
                    <p className="mt-2 text-sm text-text-muted">
                      Last updated {formatRelativeTime(domain.lastUpdated)}
                    </p>
                  ) : null}
                  {evidenceLine ? (
                    <p className="mt-2 text-sm text-text-muted">
                      {evidenceLine}
                    </p>
                  ) : null}
                </div>
              )
            })}
          </div>
          {!decisionDataHealth && dataFreshnessStatus?.status ? (
            <p className="text-sm text-text-muted">
              {dataFreshnessStatus.status === 'critical'
                ? 'Overdue'
                : dataFreshnessStatus.status === 'warning'
                  ? 'Needs attention'
                  : dataFreshnessStatus.status === 'success'
                    ? 'Current'
                    : formatEnumLabel(dataFreshnessStatus.status, 'Unknown')}
            </p>
          ) : null}
          {!decisionDataHealth && dataFreshnessStatus?.message ? (
            <p className="text-sm text-text-muted">
              {dataFreshnessStatus.message}
            </p>
          ) : null}
          {dataFreshnessStatus?.remediationsTriggered ? (
            <p className="text-sm text-text-muted">
              Auto-fixes ran{' '}
              {formatInteger(dataFreshnessStatus.remediationsTriggered)} time
              {dataFreshnessStatus.remediationsTriggered === 1 ? '' : 's'} in
              the latest check.
            </p>
          ) : null}
          {dataFreshnessStatus?.error ? (
            <p className="text-sm text-loss">
              Data recency issue: {dataFreshnessStatus.error}
            </p>
          ) : null}
          {workflowHealth ? (
            <div className="space-y-2 text-sm text-text-muted">
              <p>
                {completedWorkflowCount > 0
                  ? `${formatPercent(workflowHealth.successRate)} of ${formatInteger(completedWorkflowCount)} completed automation runs finished successfully in the last 24h.`
                  : workflowHealth.blockedWorkflows > 0
                    ? `No automation runs finished in the last 24h. ${formatInteger(workflowHealth.blockedWorkflows)} ${workflowHealth.blockedWorkflows === 1 ? 'is' : 'are'} stuck or overdue.`
                    : totalWorkflowCount && totalWorkflowCount > 0
                      ? 'Automation started in the last 24h, but nothing has finished yet.'
                      : 'No automation runs were recorded in the last 24h.'}
              </p>
              <p>
                {formatInteger(workflowHealth.failedWorkflows)} failed ·{' '}
                {formatInteger(workflowHealth.blockedWorkflows)} stuck
              </p>
              <p>
                {workflowHealth.lastSuccessfulWorkflow
                  ? `Last success ${formatRelativeTime(workflowHealth.lastSuccessfulWorkflow)}`
                  : 'No successful automation run recorded yet.'}
              </p>
              {workflowHealth.lastSuccessfulType ? (
                <p>
                  Last successful automation:{' '}
                  {formatLabel(workflowHealth.lastSuccessfulType)}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : (
        <EmptyPanelMessage message="No decision-data health summary is available right now." />
      )}
    </SectionCard>
  )
}
