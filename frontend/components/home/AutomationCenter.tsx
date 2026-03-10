'use client'

import { Bot, Clock3, ShieldCheck, TriangleAlert } from 'lucide-react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { useRunJennyRoutine } from '@/lib/hooks/usePortfolio'
import { useAutomationCenter } from '@/lib/hooks/useHomeActionQueue'
import { useUpdatePreferences } from '@/lib/hooks/usePreferences'

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
  const { data, isLoading, error } = useAutomationCenter()
  const runJennyRoutine = useRunJennyRoutine()
  const updatePreferences = useUpdatePreferences()

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
            onClick={() => runJennyRoutine.mutate('weeklyLearning')}
            disabled={runJennyRoutine.isPending}
          >
            Refresh learning
          </Button>
          <Button
            size="sm"
            onClick={() => runJennyRoutine.mutate('dailyOperator')}
            disabled={runJennyRoutine.isPending}
          >
            Run daily review
          </Button>
        </>
      }
    >
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
        <div className="rounded-2xl border border-loss/30 bg-loss/10 p-4 text-sm text-loss">
          Failed to load automation guardrails.
        </div>
      ) : null}

      {!isLoading && !error && data ? (
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="space-y-3">
            {data.guardrails.map((guardrail) => (
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
                    disabled={updatePreferences.isPending}
                    onCheckedChange={(checked) =>
                      updatePreferences.mutate({
                        [
                          GUARDRAIL_TO_PREFERENCE_FIELD[
                            guardrail.key as keyof typeof GUARDRAIL_TO_PREFERENCE_FIELD
                          ]
                        ]: checked,
                      })
                    }
                  />
                </div>
                <p className="mt-2 text-sm text-text-muted">{guardrail.detail}</p>
                <div className="mt-3 inline-flex rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-primary">
                  {guardrail.value}
                </div>
              </div>
            ))}

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
            {data.recentRuns.map((run) => (
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
                <div className="mt-3 flex items-center gap-3 text-xs text-text-muted">
                  <span className="inline-flex items-center gap-1">
                    <Clock3 className="h-3.5 w-3.5" />
                    {formatTimestamp(run.completedAt ?? run.startedAt)}
                  </span>
                  <span>{run.triggeredBy}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </SectionCard>
  )
}
