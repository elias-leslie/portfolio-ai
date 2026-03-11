'use client'

import { Bot, Clock3, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { useRunJennyRoutine } from '@/lib/hooks/usePortfolio'
import { useAutomationCenter } from '@/lib/hooks/useHomeActionQueue'
import { useUpdatePreferences } from '@/lib/hooks/usePreferences'
import { formatRelativeTime } from '@/lib/utils'

const GUARDRAIL_TO_PREFERENCE_FIELD = {
  thesis_generation_enabled: 'thesisGenerationEnabled',
  auto_remove_on_invalidation: 'autoRemoveOnInvalidation',
  auto_trim_enabled: 'autoTrimEnabled',
} as const

function formatTimestamp(value: string | null) {
  if (!value) {
    return 'Running'
  }
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function AutomationCenter() {
  const { data, isLoading, error, refetch, isFetching } = useAutomationCenter()
  const runJennyRoutine = useRunJennyRoutine()
  const updatePreferences = useUpdatePreferences()
  const isMutating = runJennyRoutine.isPending || updatePreferences.isPending

  return (
    <SectionCard
      variant="surface"
      title="Automation Center"
      description="Guardrails, recent runs, and manual controls for the agentic parts of the product."
      actions={
        <>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              void refetch()
            }}
            disabled={isFetching || isMutating}
            aria-busy={isFetching}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => runJennyRoutine.mutate('weeklyLearning')}
            disabled={isMutating}
            aria-busy={runJennyRoutine.isPending}
          >
            Refresh learning
          </Button>
          <Button
            size="sm"
            onClick={() => runJennyRoutine.mutate('dailyOperator')}
            disabled={isMutating}
            aria-busy={runJennyRoutine.isPending}
          >
            Run daily review
          </Button>
        </>
      }
    >
      {!isLoading && !error && data ? (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-sm text-text-muted">
          <span>
            {data.guardrails.length} guardrail{data.guardrails.length === 1 ? '' : 's'} ·{' '}
            {data.recentRuns.length} recent run{data.recentRuns.length === 1 ? '' : 's'}
          </span>
          <span>Updated {formatRelativeTime(data.generatedAt)}</span>
        </div>
      ) : null}

      {isLoading ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {[...Array(4)].map((_, index) => (
            <div
              key={`automation-skeleton-${index}`}
              className="h-24 animate-pulse rounded-2xl bg-surface-muted/40"
            />
          ))}
        </div>
      ) : null}

      {!isLoading && error ? (
        <LoadErrorState
          title="Failed to load automation guardrails."
          detail="Retry to refresh runtime controls and the recent automation history."
          onRetry={() => {
            void refetch()
          }}
          isRetrying={isFetching}
        />
      ) : null}

      {!isLoading && !error && data ? (
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="space-y-3">
            {data.guardrails.length === 0 ? (
              <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text-muted">
                No automation guardrails are configured yet. Add runtime preferences so daily
                reviews and thesis generation are easier to trust.
              </div>
            ) : (
              data.guardrails.map((guardrail) => {
                const preferenceField =
                  GUARDRAIL_TO_PREFERENCE_FIELD[
                    guardrail.key as keyof typeof GUARDRAIL_TO_PREFERENCE_FIELD
                  ]

                return (
                  <div
                    key={guardrail.key}
                    className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4 text-primary" />
                        <div>
                          <p className="text-sm font-semibold text-text">{guardrail.label}</p>
                          <p className="text-xs text-text-muted">
                            {guardrail.source === 'preferences'
                              ? 'Runtime override'
                              : 'Using rules default'}
                          </p>
                        </div>
                      </div>
                      <Switch
                        checked={guardrail.enabled}
                        aria-label={`Toggle ${guardrail.label}`}
                        disabled={isMutating || !preferenceField}
                        onCheckedChange={(checked) => {
                          if (!preferenceField) {
                            return
                          }

                          updatePreferences.mutate({
                            [preferenceField]: checked,
                          })
                        }}
                      />
                    </div>
                    <p className="mt-2 text-sm text-text-muted">{guardrail.detail}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge variant={guardrail.enabled ? 'success' : 'secondary'}>
                        {guardrail.enabled ? 'enabled' : 'disabled'}
                      </Badge>
                      <Badge variant="outline">{guardrail.value}</Badge>
                      {!preferenceField ? (
                        <Badge variant="warning">Read only</Badge>
                      ) : null}
                    </div>
                  </div>
                )
              })
            )}

            {data.warnings.length > 0 ? (
              <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-text">
                  <TriangleAlert className="h-4 w-4 text-warning" />
                  Recent warnings
                </div>
                <div className="mt-3 space-y-2">
                  {data.warnings.map((warning) => (
                    <p key={warning} className="text-sm text-text-muted">
                      {warning}
                    </p>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            {data.recentRuns.length === 0 ? (
              <div className="rounded-2xl border border-border/40 bg-surface/70 p-4 text-sm text-text-muted">
                No automation runs have been recorded yet. Kick off a manual review to confirm the
                automation path and generate fresh portfolio signals.
              </div>
            ) : (
              data.recentRuns.map((run) => (
                <div
                  key={run.id}
                  className="rounded-2xl border border-border/40 bg-surface/70 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <Bot className="h-4 w-4 text-primary" />
                        <p className="text-sm font-semibold text-text">{run.label}</p>
                      </div>
                      <p className="mt-2 text-sm text-text-muted">{run.detail}</p>
                    </div>
                    <span className="rounded-full bg-surface-muted/60 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-text">
                      {run.status}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-text-muted">
                    <span className="inline-flex items-center gap-1">
                      <Clock3 className="h-3.5 w-3.5" />
                      {formatTimestamp(run.completedAt)}
                    </span>
                    <span>Started {formatRelativeTime(run.startedAt)}</span>
                    <span>{run.triggeredBy}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </SectionCard>
  )
}
