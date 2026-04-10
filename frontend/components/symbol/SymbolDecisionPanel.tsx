'use client'

import { ArrowRight } from 'lucide-react'
import Link from 'next/link'
import { SectionCard } from '@/components/shared/SectionCard'
import {
  CurrentExposure,
  SourceAuditTrail,
} from '@/components/symbol/SymbolDecisionContext'
import { Badge } from '@/components/ui/badge'
import type {
  JennyNotification,
  JennySymbolReview,
  JennyTradeReview,
} from '@/lib/api/portfolio'
import type {
  SymbolDecisionSection,
  SymbolIntelligence,
  SymbolRecommendationSection,
} from '@/lib/api/symbols'
import {
  formatDecisionMeta,
  formatDecisionSeverity,
} from '@/lib/decision'
import {
  formatCurrency,
  formatEnumLabel,
} from '@/lib/formatters'
import { formatRelativeTime } from '@/lib/utils'
import {
  formatIfNotHeldReasoning,
  formatTenPointConfidence,
} from './symbol-formatters'

type DecisionActionGroup = 'buy' | 'hold' | 'review' | 'trim' | 'exit' | 'avoid'

function actionGroup(action?: string | null): DecisionActionGroup | null {
  const normalized = action?.toLowerCase() ?? ''

  if (
    normalized.includes('exit') ||
    normalized.includes('sell') ||
    normalized.includes('stop')
  ) {
    return 'exit'
  }
  if (normalized.includes('trim') || normalized.includes('reduce')) {
    return 'trim'
  }
  if (normalized.includes('avoid')) {
    return 'avoid'
  }
  if (
    normalized.includes('review') ||
    normalized.includes('recheck') ||
    normalized.includes('monitor')
  ) {
    return 'review'
  }
  if (
    normalized.includes('buy') ||
    normalized.includes('initiate') ||
    normalized.includes('add')
  ) {
    return 'buy'
  }
  if (normalized.includes('hold') || normalized.includes('watch')) {
    return 'hold'
  }

  return null
}

function hasMaterialConflict(
  decision?: SymbolDecisionSection | null,
  recommendation?: SymbolRecommendationSection | null,
) {
  if (!decision || !recommendation || decision.sourceKind === 'live_signal_model') {
    return false
  }

  const decisionGroup = actionGroup(decision.action)
  const recommendationGroup = actionGroup(recommendation.action)

  return Boolean(
    decisionGroup &&
      recommendationGroup &&
      decisionGroup !== recommendationGroup,
  )
}

function shouldShowTradingSetup(data?: SymbolIntelligence | null) {
  const decision = data?.decision
  if (!decision || !data?.trading || decision.sourceKind !== 'live_signal_model') {
    return false
  }

  const group = actionGroup(decision.action)
  return group === 'buy' || group === 'hold' || group === 'review'
}

function formatLiveSignalEvidence(data?: SymbolIntelligence | null) {
  const parts = [
    data?.scores?.overall != null
      ? `Score ${data.scores.overall.toFixed(0)}`
      : null,
    data?.signal?.type
      ? formatEnumLabel(data.signal.type, 'Signal unavailable')
      : null,
    data?.signal?.strength != null
      ? `${data.signal.strength}/10 confidence`
      : null,
    data?.generatedAt ? `Updated ${formatRelativeTime(data.generatedAt)}` : null,
  ].filter((part): part is string => Boolean(part))

  return parts.length > 0 ? parts.join(' · ') : null
}

function DecisionReasonList({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/40 bg-surface-muted/10 p-4 text-sm text-text-muted">
        No Jenny/data reasoning is attached to this decision yet.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {reasons.slice(0, 4).map((reason, idx) => (
        <div
          key={`${reason}-${idx}`}
          className="rounded-xl border border-border/30 border-l-2 border-l-accent/50 bg-surface/50 p-4 text-sm leading-relaxed text-text-muted"
          style={{ animationDelay: `${idx * 60}ms` }}
        >
          {reason}
        </div>
      ))}
    </div>
  )
}

function TradingSetup({ data }: { data: SymbolIntelligence }) {
  if (!data.trading) {
    return null
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Buy zone / downside limit
        </p>
        <p className="mt-2 text-sm tabular-nums text-text">
          {formatCurrency(data.trading.entryPrice)} /{' '}
          {formatCurrency(data.trading.stopLoss)}
        </p>
      </div>
      <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Upside target / starter size
        </p>
        <p className="mt-2 text-sm tabular-nums text-text">
          {formatCurrency(data.trading.profitTarget)} /{' '}
          {data.trading.positionSizeShares ?? '—'} shares
        </p>
      </div>
      <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Confidence / Risk
        </p>
        <p className="mt-2 text-sm text-text">
          {formatTenPointConfidence(data.trading.confidence)} ·{' '}
          {data.trading.riskLevel ?? 'Risk unavailable'}
        </p>
      </div>
      <div className="rounded-2xl border border-border/40 bg-surface/60 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Typical holding time
        </p>
        <p className="mt-2 text-sm text-text">
          {data.trading.holdingPeriod ?? '—'} ·{' '}
          {data.trading.style ?? 'Unknown style'}
        </p>
      </div>
    </div>
  )
}

export function SymbolDecisionPanel({
  symbol,
  data,
  activeNotification,
  latestReview,
  tradeReviews,
  positionSummary,
  portfolioContextParts,
}: {
  symbol: string
  data?: SymbolIntelligence | null
  activeNotification: JennyNotification | null
  latestReview?: JennySymbolReview | null
  tradeReviews: JennyTradeReview[]
  positionSummary: string
  portfolioContextParts: string[]
}) {
  const decision = data?.decision ?? null
  const decisionMeta = formatDecisionMeta(decision)
  const conflict = hasMaterialConflict(decision, data?.recommendation)
  const liveSignalEvidence = formatLiveSignalEvidence(data)
  const showTradingSetup = shouldShowTradingSetup(data)
  const isHeld = Boolean(data?.portfolio?.held)
  const showIfNotHeld =
    !isHeld &&
    decision?.sourceKind === 'live_signal_model' &&
    Boolean(data?.recommendation?.ifNotHeld)

  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <SectionCard
        variant="surface"
        title="Decision Memo"
        description="Current decision and source data."
      >
        <div className="space-y-4">
          <div className="rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/10 via-surface/70 to-surface-muted/20 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-text-muted">
                  Current decision
                </p>
                <p className="mt-2 font-display italic text-3xl text-text">
                  {decision?.headline ?? 'Decision unavailable'}
                </p>
              </div>
              {decision?.severity ? (
                <Badge variant="outline">
                  {formatDecisionSeverity(decision.severity)}
                </Badge>
              ) : null}
            </div>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-text-muted">
              {decision?.summary ??
                'Jenny does not have enough decision context for this symbol yet.'}
            </p>
            {decisionMeta ? (
              <p className="mt-3 text-xs uppercase tracking-[0.18em] text-text-muted">
                {decisionMeta}
              </p>
            ) : null}
          </div>

          <div>
            <p className="mb-3 text-sm font-semibold text-text">
              Why Jenny is showing this
            </p>
            <DecisionReasonList reasons={decision?.reasoning ?? []} />
          </div>

          {conflict ? (
            <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-text">
              <p className="font-semibold">Signal disagreement</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div className="rounded-xl border border-warning/20 bg-surface/40 p-3">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
                    Live model
                  </p>
                  <p className="mt-1 font-semibold text-text">
                    {formatEnumLabel(data?.recommendation?.action, 'Review')}
                  </p>
                </div>
                <div className="rounded-xl border border-warning/20 bg-surface/40 p-3">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
                    Current decision
                  </p>
                  <p className="mt-1 font-semibold text-text">
                    {decision?.headline ??
                      formatEnumLabel(decision?.action, 'Decision unavailable')}
                  </p>
                </div>
              </div>
              {liveSignalEvidence ? (
                <p className="mt-3 text-xs uppercase tracking-[0.16em] text-text-muted">
                  {liveSignalEvidence}
                </p>
              ) : null}
            </div>
          ) : null}

          {!conflict &&
          decision?.sourceKind !== 'live_signal_model' &&
          liveSignalEvidence ? (
            <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4 text-sm text-text-muted">
              <p className="font-semibold text-text">Supporting live data</p>
              <p className="mt-2">{liveSignalEvidence}</p>
            </div>
          ) : null}

          {showTradingSetup && data ? <TradingSetup data={data} /> : null}

          {showIfNotHeld && data?.recommendation?.ifNotHeld ? (
            <div className="rounded-2xl border border-border/40 bg-primary/5 p-4 text-sm text-text">
              If you do not own it yet:{' '}
              {formatEnumLabel(data.recommendation.ifNotHeld.action, 'Review')}{' '}
              ·{' '}
              {formatIfNotHeldReasoning(
                data.recommendation.ifNotHeld.reasoning,
              )}
              {data.recommendation.ifNotHeld.sizePct != null
                ? ` · Starter size ${data.recommendation.ifNotHeld.sizePct.toFixed(1)}%`
                : ''}
            </div>
          ) : null}

          <Link
            href="/portfolio?tab=holdings&highlight=concentration#portfolio-overview"
            className="group flex items-center justify-between rounded-2xl border border-border/40 bg-surface-muted/20 p-4 text-sm text-text transition-all duration-200 hover:border-primary/40 hover:bg-surface-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <span>Review concentration in Holdings</span>
            <ArrowRight className="h-4 w-4 text-text-muted transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary" />
          </Link>
        </div>
      </SectionCard>

      <div className="space-y-4">
        <CurrentExposure
          data={data}
          positionSummary={positionSummary}
          portfolioContextParts={portfolioContextParts}
        />
        <SourceAuditTrail
          symbol={symbol}
          activeNotification={activeNotification}
          latestReview={latestReview}
          tradeReviews={tradeReviews}
        />
      </div>
    </div>
  )
}
