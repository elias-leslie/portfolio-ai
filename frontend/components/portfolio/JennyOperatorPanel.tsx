'use client'

import { Brain, CheckCircle2, RefreshCw, Siren, TrendingUp } from 'lucide-react'
import Link from 'next/link'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type {
  JennyAgentScorecard,
  JennyNotification,
  JennySymbolReview,
} from '@/lib/api/portfolio'
import {
  useAcknowledgeJennyNotification,
  useJennyDashboard,
  useRunJennyRoutine,
} from '@/lib/hooks/usePortfolio'

function verdictLabel(verdict: string) {
  switch (verdict) {
    case 'buy':
      return 'Potential buy'
    case 'trim':
      return 'Trim prompt'
    case 'exit':
      return 'Exit prompt'
    case 'hold':
      return 'Keep holding'
    case 'avoid':
      return 'Skip for now'
    default:
      return 'Needs review'
  }
}

function managementLabel(action: string | null | undefined) {
  switch (action) {
    case 'trim':
      return 'Trim now'
    case 'de_risk':
      return 'De-risk now'
    case 'exit':
      return 'Exit now'
    case 'review':
      return 'Recheck now'
    case 'hold':
      return 'Hold steady'
    default:
      return null
  }
}

function severityTone(severity: string) {
  switch (severity) {
    case 'critical':
      return 'border-loss/30 bg-loss/10'
    case 'warning':
      return 'border-warning/30 bg-warning/10'
    default:
      return 'border-primary/20 bg-primary/5'
  }
}

function formatTimestamp(value: string | null) {
  if (!value) {
    return 'Not yet'
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

function topStrength(scorecard: JennyAgentScorecard) {
  return scorecard.strengths[0] ?? 'Still gathering enough history to judge.'
}

function scoreItems(scorecard: JennyAgentScorecard) {
  return [
    ['Entries', scorecard.entryQualityScore],
    ['Risk', scorecard.riskJudgmentScore],
    ['Exits', scorecard.exitTimingScore],
    ['Noise', scorecard.alertDisciplineScore],
  ].filter(([, value]) => value !== null) as Array<[string, number]>
}

function reviewSubtitle(review: JennySymbolReview) {
  const confidence =
    review.averageConfidence !== null
      ? `${Math.round(review.averageConfidence * 100)}% confidence`
      : 'Confidence still forming'
  return `${verdictLabel(review.finalVerdict)} · ${confidence}`
}

function notificationActionLabel(notification: JennyNotification) {
  if (notification.category.includes('exit')) {
    return 'Review exit case'
  }
  if (notification.category.includes('trim')) {
    return 'Review trim case'
  }
  if (notification.category === 'watchlist_buy_candidate') {
    return 'Inspect setup'
  }
  return 'Mark reviewed'
}

function severityCounts(notifications: JennyNotification[]) {
  return notifications.reduce(
    (counts, notification) => {
      if (notification.severity === 'critical') {
        counts.critical += 1
      } else if (notification.severity === 'warning') {
        counts.warning += 1
      } else {
        counts.other += 1
      }
      return counts
    },
    { critical: 0, warning: 0, other: 0 },
  )
}

export function JennyOperatorPanel() {
  const { data, isLoading, error, refetch, isFetching } = useJennyDashboard()
  const runRoutine = useRunJennyRoutine()
  const acknowledge = useAcknowledgeJennyNotification()

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="h-44 animate-pulse rounded bg-surface-muted/60" />
      </Card>
    )
  }

  if (!data && error) {
    return (
      <LoadErrorState
        title="Failed to load Jenny operator status."
        detail="Retry to refresh Jenny’s latest routines, alerts, and agent scorecards."
        onRetry={() => {
          void refetch()
        }}
        isRetrying={isFetching}
      />
    )
  }

  const dashboard = data
  const latestRoutine = dashboard?.routines[0]
  const topReviews = dashboard?.symbolReviews.slice(0, 3) ?? []
  const topNotifications = dashboard?.notifications.slice(0, 4) ?? []
  const topScorecards = dashboard?.scorecards.slice(0, 3) ?? []
  const notificationCounts = severityCounts(dashboard?.notifications ?? [])

  return (
    <Card className="p-6">
      {error ? (
        <div className="mb-4 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Jenny data is partially stale. The latest cached operator view is shown below.
        </div>
      ) : null}

      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-primary" />
            <h3 className="font-display text-lg tracking-tight text-text">Jenny Operator</h3>
          </div>
          <p className="mt-1 text-sm text-text-muted">
            Jenny reviews your positions, keeps score on her agents, and only
            surfaces actions worth your attention.
          </p>
          <p className="mt-2 text-xs text-text-muted">
            Last routine: {latestRoutine?.summary ?? 'No Jenny routine has run yet.'}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Updated {formatTimestamp(latestRoutine?.completedAt ?? null)}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {dashboard?.notifications.length ?? 0} alerts · {dashboard?.symbolReviews.length ?? 0} symbol reviews ·{' '}
            {dashboard?.scorecards.length ?? 0} scorecards
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => runRoutine.mutate('dailyOperator')}
            disabled={runRoutine.isPending}
            aria-busy={runRoutine.isPending}
          >
            <RefreshCw
              className={cn('mr-2 h-4 w-4', runRoutine.isPending && 'animate-spin')}
            />
            Run Review
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => runRoutine.mutate('weeklyLearning')}
            disabled={runRoutine.isPending}
            aria-busy={runRoutine.isPending}
          >
            <TrendingUp className="mr-2 h-4 w-4" />
            Refresh Learning
          </Button>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-sm text-text-muted">
        Latest routine {latestRoutine?.status ?? 'not_run'}
        {latestRoutine?.symbolsScanned != null ? ` · ${latestRoutine.symbolsScanned} symbols scanned` : ''}
        {latestRoutine?.notificationsCreated != null
          ? ` · ${latestRoutine.notificationsCreated} alert${latestRoutine.notificationsCreated === 1 ? '' : 's'} created`
          : ''}
        {' · '}
        {notificationCounts.critical} critical
        {' · '}
        {notificationCounts.warning} warning
        {' · '}
        {notificationCounts.other} other
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-3">
          <div>
            <h3 className="font-display text-base tracking-tight text-text">Action queue</h3>
            <p className="mt-1 text-sm text-text-muted">
              Only urgent portfolio actions and high-conviction opportunities.
            </p>
          </div>

          {topNotifications.length === 0 ? (
            <div className="rounded-xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
              Jenny does not see anything urgent right now. Doing nothing is a
              valid choice.
            </div>
          ) : (
            topNotifications.map((notification) => (
              <div
                key={notification.id}
                className={cn('rounded-xl border p-4', severityTone(notification.severity))}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-text">
                      <Siren className="h-4 w-4" />
                      {notification.title}
                    </div>
                    <p className="mt-1 text-sm text-text-muted">
                      {notification.detail}
                    </p>
                    {notification.recommendation ? (
                      <p className="mt-2 text-sm text-text">
                        Next step: {notification.recommendation}
                      </p>
                    ) : null}
                  </div>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => acknowledge.mutate(notification.id)}
                    disabled={acknowledge.isPending}
                  >
                    {notificationActionLabel(notification)}
                  </Button>
                </div>
              </div>
            ))
          )}
          {dashboard && dashboard.notifications.length > topNotifications.length ? (
            <p className="text-xs text-text-muted">
              Showing the newest {topNotifications.length} of {dashboard.notifications.length} alerts.
            </p>
          ) : null}
        </div>

        <div className="space-y-4">
          <div>
            <h3 className="font-display text-base tracking-tight text-text">Top symbol reviews</h3>
            <div className="mt-3 space-y-3">
              {topReviews.length === 0 ? (
                <div className="rounded-xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text-muted">
                  Jenny has not reviewed any symbols yet.
                </div>
              ) : (
                topReviews.map((review) => (
                  <div
                    key={review.symbol}
                    className="rounded-xl border border-border/40 bg-surface-muted/20 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-text">
                          <Link href={`/symbols/${review.symbol}`} className="hover:underline">
                            {review.symbol}
                          </Link>
                        </p>
                        <p className="mt-1 text-sm text-text-muted">
                          {reviewSubtitle(review)}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-text">
                          {verdictLabel(review.finalVerdict)}
                        </span>
                        {managementLabel(review.managementAction) ? (
                          <span className="rounded-full bg-warning/10 px-2.5 py-1 text-[11px] font-medium text-text">
                            {managementLabel(review.managementAction)}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    {review.reasons[0] ? (
                      <p className="mt-3 text-sm text-text-muted">
                        {review.reasons[0]}
                      </p>
                    ) : null}
                    {review.managementDetail ? (
                      <p className="mt-2 text-sm text-text">
                        {review.managementDetail}
                      </p>
                    ) : null}
                  </div>
                ))
              )}
            </div>
            {dashboard && dashboard.symbolReviews.length > topReviews.length ? (
              <p className="text-xs text-text-muted">
                Showing the top {topReviews.length} of {dashboard.symbolReviews.length} symbol reviews.
              </p>
            ) : null}
          </div>

          <div>
            <h3 className="font-display text-base tracking-tight text-text">Agent scorecards</h3>
            <div className="mt-3 space-y-3">
              {topScorecards.length === 0 ? (
                <div className="rounded-xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text-muted">
                  Jenny needs more completed trades before agent scorecards mean
                  anything.
                </div>
              ) : (
                topScorecards.map((scorecard) => (
                  <div
                    key={scorecard.agentName}
                    className="rounded-xl border border-border/40 bg-surface-muted/20 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 text-sm font-semibold text-text">
                        <CheckCircle2 className="h-4 w-4 text-primary" />
                        {scorecard.agentName}
                      </div>
                      <span className="text-xs text-text-muted">
                        {scorecard.completedReviews} reviewed trades
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-text-muted">
                      {topStrength(scorecard)}
                    </p>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-text-muted">
                      {scoreItems(scorecard).map(([label, value]) => (
                        <div
                          key={label}
                          className="rounded-lg border border-border/40 bg-surface/40 px-2.5 py-2"
                        >
                          <div>{label}</div>
                          <div className="mt-1 text-sm font-semibold text-text">
                            {Math.round(value)}/100
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
            {dashboard && dashboard.scorecards.length > topScorecards.length ? (
              <p className="text-xs text-text-muted">
                Showing the strongest {topScorecards.length} of {dashboard.scorecards.length} scorecards.
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </Card>
  )
}
