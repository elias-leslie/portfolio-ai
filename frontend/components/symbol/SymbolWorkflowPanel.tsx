'use client'

import { useState } from 'react'
import { ArrowRight, GitBranch, RotateCcw } from 'lucide-react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  useRecordSymbolWorkflowOutcome,
  useSymbolWorkflow,
  useTransitionSymbolWorkflow,
} from '@/lib/hooks/useSymbolIntelligence'

function formatStage(stage: string) {
  return stage.replaceAll('_', ' ')
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return '—'
  }
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function SymbolWorkflowPanel({
  symbol,
  latestReview,
}: {
  symbol: string
  latestReview?: {
    finalVerdict?: string | null
    managementAction?: string | null
  } | null
}) {
  const { data, isLoading, error, refetch, isFetching } = useSymbolWorkflow(symbol)
  const transitionWorkflow = useTransitionSymbolWorkflow(symbol)
  const recordOutcome = useRecordSymbolWorkflowOutcome(symbol)
  const [outcomeNote, setOutcomeNote] = useState('')

  return (
    <SectionCard
      variant="surface"
      title="Workflow Loop"
      description="Persist the real state of this symbol instead of rediscovering it every time."
    >
      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[...Array(4)].map((_, index) => (
            <div
              key={`workflow-skeleton-${index}`}
              className="skeleton rounded-2xl h-20"
            />
          ))}
        </div>
      ) : null}

      {!isLoading && error ? (
        <LoadErrorState
          title="Failed to load the symbol workflow."
          detail="Retry to refresh the current stage, available transitions, and recent history."
          onRetry={() => {
            void refetch()
          }}
          isRetrying={isFetching}
        />
      ) : null}

      {!isLoading && !error && data ? (
        <div className="space-y-5">
          <div className="grid gap-4 lg:grid-cols-[0.7fr_1.3fr]">
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Current stage
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">{formatStage(data.stage)}</p>
              <p className="mt-2 text-sm text-text-muted">{data.summary}</p>
              {data.notes ? (
                <p className="mt-3 text-sm text-text-muted">{data.notes}</p>
              ) : null}
              <p className="mt-4 text-xs text-text-muted">
                Updated {formatTimestamp(data.lastTransitionAt)} by {data.updatedBy}
              </p>
              {data.nextReviewAt ? (
                <p className="mt-1 text-xs text-text-muted">
                  Review target {formatTimestamp(data.nextReviewAt)}
                </p>
              ) : null}
              {data.position ? (
                <div className="mt-4 rounded-xl border border-border/40 bg-surface/70 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Live position
                  </p>
                  <p className="mt-2 text-sm text-text">
                    {data.position.shares.toFixed(2)} shares · basis ${data.position.costBasis.toFixed(2)}
                  </p>
                  <p className="mt-1 text-sm text-text-muted">
                    {data.position.marketValue !== null
                      ? `$${data.position.marketValue.toFixed(0)} market value`
                      : 'Market value unavailable'}
                    {data.position.gainPct !== null
                      ? ` · ${data.position.gainPct >= 0 ? '+' : ''}${data.position.gainPct.toFixed(1)}%`
                      : ''}
                  </p>
                </div>
              ) : null}
            </div>

            <div className="rounded-2xl border border-border/40 bg-surface/70 p-4">
              <p className="text-sm font-semibold text-text">Available transitions</p>
              {data.availableTransitions.length === 0 ? (
                <div className="mt-4 rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text-muted">
                  No stage transitions are available right now. This symbol is waiting on the next
                  review or outcome capture.
                </div>
              ) : (
                <div className="mt-4 flex flex-wrap gap-2">
                  {data.availableTransitions.map((stage) => (
                    <Button
                      key={stage}
                      size="sm"
                      variant={stage === 'invalidated' ? 'destructive' : 'outline'}
                      onClick={() => transitionWorkflow.mutate({ stage })}
                      disabled={transitionWorkflow.isPending}
                      aria-busy={transitionWorkflow.isPending}
                    >
                      {stage === 'discover' ? (
                        <RotateCcw className="mr-2 h-4 w-4" />
                      ) : (
                        <ArrowRight className="mr-2 h-4 w-4" />
                      )}
                      Move to {formatStage(stage)}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-border/40 bg-surface/70 p-4">
            <p className="text-sm font-semibold text-text">Outcome capture</p>
            <p className="mt-2 text-sm text-text-muted">
              Record the real decision on the live position so future reviews remember the context.
            </p>
            <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto]">
              <Input
                value={outcomeNote}
                onChange={(event) => setOutcomeNote(event.target.value)}
                placeholder="Optional note: why did you hold, trim, exit, or invalidate?"
              />
              <div className="flex flex-wrap gap-2">
                {['hold', 'trim', 'exit', 'invalidate'].map((action) => (
                  <Button
                    key={action}
                    size="sm"
                    variant={action === 'invalidate' ? 'destructive' : 'outline'}
                    onClick={() =>
                      recordOutcome.mutate({
                        action,
                        note: outcomeNote || `Recorded ${action} decision from symbol workspace.`,
                        jennyVerdict: latestReview?.finalVerdict ?? null,
                        managementAction: latestReview?.managementAction ?? null,
                      })
                    }
                    disabled={recordOutcome.isPending}
                    aria-busy={recordOutcome.isPending}
                  >
                    {action === 'exit' ? 'Record exit' : action === 'hold' ? 'Record hold' : action === 'trim' ? 'Record trim' : 'Invalidate'}
                  </Button>
                ))}
              </div>
            </div>
            {data.latestOutcome ? (
              <div className="mt-4 rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
                <p className="text-sm font-semibold text-text">
                  Latest recorded outcome: {data.latestOutcome.action}
                </p>
                <p className="mt-2 text-sm text-text-muted">{data.latestOutcome.note}</p>
                <p className="mt-2 text-xs text-text-muted">
                  {formatTimestamp(data.latestOutcome.createdAt)}
                  {data.latestOutcome.jennyVerdict
                    ? ` · Jenny ${data.latestOutcome.jennyVerdict}`
                    : ''}
                </p>
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            <p className="text-sm font-semibold text-text">Recent history</p>
            {data.history.length === 0 ? (
              <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text-muted">
                No workflow history yet. The first transition will start the audit trail.
              </div>
            ) : (
              data.history.map((event) => (
                <div
                  key={event.id}
                  className="rounded-2xl border border-border/40 bg-surface-muted/10 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm font-semibold text-text">
                      <GitBranch className="h-4 w-4 text-primary" />
                      <span>
                        {event.fromStage ? formatStage(event.fromStage) : 'System'} to{' '}
                        {formatStage(event.toStage)}
                      </span>
                    </div>
                    <span className="text-xs text-text-muted">
                      {formatTimestamp(event.createdAt)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">{event.note}</p>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </SectionCard>
  )
}
