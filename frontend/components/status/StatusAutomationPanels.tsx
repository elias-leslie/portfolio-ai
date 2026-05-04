'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type { RecentRemediation, StaleMaintenanceRun } from '@/lib/api/health'
import { formatHours, formatInteger } from '@/lib/formatters'
import { formatDateTime, formatRelativeTime } from '@/lib/utils'
import { formatLabel, remediationPresentation } from './statusUtils'

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
                  <p className="text-sm font-semibold text-text">
                    {event.tableName}
                  </p>
                  <Badge variant={presentation.badgeVariant}>
                    {presentation.badgeLabel}
                  </Badge>
                </div>
                <p className="mt-2 text-sm text-text-muted">
                  Detected {formatDateTime(event.triggeredAt)} · Age{' '}
                  {formatHours(event.ageHours)} / alert threshold{' '}
                  {formatHours(event.thresholdHours)}
                </p>
                {event.occurrenceCount && event.occurrenceCount > 1 ? (
                  <p className="mt-2 text-sm text-text-muted">
                    This happened {formatInteger(event.occurrenceCount)} times
                    in the last 24h.
                  </p>
                ) : null}
                {presentation.detail ? (
                  <p className="mt-2 text-sm text-text-muted">
                    {presentation.detail}
                  </p>
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
              <p className="text-sm font-semibold text-text">
                {formatLabel(run.taskName)}
              </p>
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
