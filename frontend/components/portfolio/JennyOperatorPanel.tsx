'use client'

import { Brain, CheckCircle2, RefreshCw, Siren, TrendingUp } from 'lucide-react'
import { Card } from '@/components/ui/card'
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

export function JennyOperatorPanel() {
  const { data, isLoading } = useJennyDashboard()
  const runRoutine = useRunJennyRoutine()
  const acknowledge = useAcknowledgeJennyNotification()

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="h-44 animate-pulse rounded bg-surface-muted/60" />
      </Card>
    )
  }

  const dashboard = data
  const latestRoutine = dashboard?.routines[0]
  const topReviews = dashboard?.symbolReviews.slice(0, 3) ?? []
  const topNotifications = dashboard?.notifications.slice(0, 4) ?? []
  const topScorecards = dashboard?.scorecards.slice(0, 3) ?? []

  return (
    <Card className="p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-text">
            <Brain className="h-4 w-4 text-primary" />
            Jenny Operator
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
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/10 px-3 py-2 text-sm font-medium text-text transition hover:bg-primary/15 disabled:opacity-50"
            onClick={() => runRoutine.mutate('dailyOperator')}
            disabled={runRoutine.isPending}
          >
            <RefreshCw
              className={`h-4 w-4 ${runRoutine.isPending ? 'animate-spin' : ''}`}
            />
            Run Review
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-lg border border-surface-border px-3 py-2 text-sm font-medium text-text transition hover:bg-surface-muted/40 disabled:opacity-50"
            onClick={() => runRoutine.mutate('weeklyLearning')}
            disabled={runRoutine.isPending}
          >
            <TrendingUp className="h-4 w-4" />
            Refresh Learning
          </button>
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-semibold text-text">Action queue</h3>
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
                className={`rounded-xl border p-4 ${severityTone(notification.severity)}`}
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

                  <button
                    type="button"
                    className="rounded-lg border border-surface-border px-3 py-1.5 text-xs font-medium text-text transition hover:bg-surface-muted/40 disabled:opacity-50"
                    onClick={() => acknowledge.mutate(notification.id)}
                    disabled={acknowledge.isPending}
                  >
                    {notificationActionLabel(notification)}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-text">Top symbol reviews</h3>
            <div className="mt-3 space-y-3">
              {topReviews.length === 0 ? (
                <div className="rounded-xl border border-surface-border bg-surface-muted/20 p-4 text-sm text-text-muted">
                  Jenny has not reviewed any symbols yet.
                </div>
              ) : (
                topReviews.map((review) => (
                  <div
                    key={review.symbol}
                    className="rounded-xl border border-surface-border bg-surface-muted/20 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-text">
                          {review.symbol}
                        </p>
                        <p className="mt-1 text-sm text-text-muted">
                          {reviewSubtitle(review)}
                        </p>
                      </div>
                      <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-text">
                        {verdictLabel(review.finalVerdict)}
                      </span>
                    </div>
                    {review.reasons[0] ? (
                      <p className="mt-3 text-sm text-text-muted">
                        {review.reasons[0]}
                      </p>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-text">Agent scorecards</h3>
            <div className="mt-3 space-y-3">
              {topScorecards.length === 0 ? (
                <div className="rounded-xl border border-surface-border bg-surface-muted/20 p-4 text-sm text-text-muted">
                  Jenny needs more completed trades before agent scorecards mean
                  anything.
                </div>
              ) : (
                topScorecards.map((scorecard) => (
                  <div
                    key={scorecard.agentName}
                    className="rounded-xl border border-surface-border bg-surface-muted/20 p-4"
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
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </Card>
  )
}
