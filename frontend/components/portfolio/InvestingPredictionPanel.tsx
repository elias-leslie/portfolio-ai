'use client'

import { ArrowDownRight, ArrowUpRight, BrainCircuit, Gauge, Minus, Radar } from 'lucide-react'
import { useMemo, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useMarketPredictionCommittee } from '@/lib/hooks/useMarketIntelligence'
import { cn } from '@/lib/utils'

const WINDOW_OPTIONS = [1, 3, 7, 14] as const

function formatPercent(value?: number | null, digits: number = 1) {
  if (value == null || Number.isNaN(value)) return '—'
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${value.toFixed(digits)}%`
}

function formatProbability(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '—'
  return `${Math.round(value * 100)}%`
}

function directionIcon(direction: 'bullish' | 'neutral' | 'bearish') {
  if (direction === 'bullish') return ArrowUpRight
  if (direction === 'bearish') return ArrowDownRight
  return Minus
}

function directionTone(direction: 'bullish' | 'neutral' | 'bearish') {
  if (direction === 'bullish') return 'text-emerald-300 border-emerald-400/20 bg-emerald-500/10'
  if (direction === 'bearish') return 'text-rose-300 border-rose-400/20 bg-rose-500/10'
  return 'text-amber-200 border-amber-400/20 bg-amber-500/10'
}

export function InvestingPredictionPanel() {
  const [windowDays, setWindowDays] = useState<(typeof WINDOW_OPTIONS)[number]>(3)
  const { data, isLoading, error } = useMarketPredictionCommittee(windowDays)

  const leadCall = data?.leadCall
  const sectorCalls = useMemo(
    () => (data?.calls ?? []).filter((call) => call.symbol !== 'SPY'),
    [data?.calls],
  )
  const leadVotes = useMemo(
    () => (data?.votes ?? []).filter((vote) => vote.symbol === 'SPY'),
    [data?.votes],
  )
  const sourceRows = useMemo(() => {
    const leadClusters = leadCall?.topSourceClusters ?? []
    if (leadClusters.length > 0) return leadClusters
    const snapshotClusters = data?.sourceSnapshot?.clusters
    if (!snapshotClusters || typeof snapshotClusters !== 'object') return []
    return Object.entries(snapshotClusters).map(([cluster, payload]) => ({
      cluster,
      freshness:
        payload && typeof payload === 'object' && 'freshness' in payload
          ? String((payload as { freshness?: unknown }).freshness ?? '')
          : undefined,
    }))
  }, [data?.sourceSnapshot, leadCall?.topSourceClusters])

  const committeeHeadline =
    typeof data?.committeeSummary?.headline === 'string'
      ? data.committeeSummary.headline
      : 'The committee is building the latest market call.'
  const disagreementLabel =
    typeof data?.committeeSummary?.disagreementLabel === 'string'
      ? data.committeeSummary.disagreementLabel
      : 'moderate'

  const LeadIcon = directionIcon(leadCall?.directionLabel ?? 'neutral')

  return (
    <div className="space-y-4">
      <SectionCard
        title="Market Prediction Committee"
        description={committeeHeadline}
        actions={
          <div className="flex flex-wrap gap-2">
            {WINDOW_OPTIONS.map((option) => (
              <Button
                key={option}
                type="button"
                aria-label={`${option}D`}
                variant={option === windowDays ? 'default' : 'outline'}
                size="sm"
                onClick={() => setWindowDays(option)}
              >
                {option}D
              </Button>
            ))}
          </div>
        }
        variant="surface"
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          <div className="relative overflow-hidden rounded-[28px] border border-primary/20 bg-[radial-gradient(circle_at_top_left,_rgba(82,196,255,0.22),_transparent_34%),linear-gradient(135deg,rgba(18,24,38,0.96),rgba(10,14,22,0.94))] p-6 shadow-[0_0_30px_-12px_rgba(82,196,255,0.45)]">
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-text-muted">
                  Lead Market Call
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <div className={cn('rounded-2xl border px-3 py-2', directionTone(leadCall?.directionLabel ?? 'neutral'))}>
                    <LeadIcon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-4xl font-display italic tracking-tight text-text">
                      {leadCall?.symbol ?? 'SPY'}
                    </p>
                    <p className="text-sm uppercase tracking-[0.18em] text-text-muted">
                      {(leadCall?.directionLabel ?? 'neutral').toUpperCase()} · {windowDays} trading days
                    </p>
                  </div>
                </div>
              </div>
              <Badge variant="outline">Disagreement: {disagreementLabel}</Badge>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-border/30 bg-black/20 px-4 py-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">Expected move</p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {formatPercent(leadCall?.expectedMovePct)}
                </p>
              </div>
              <div className="rounded-2xl border border-border/30 bg-black/20 px-4 py-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">Probability up</p>
                <p className="mt-2 text-2xl font-semibold text-text">{formatProbability(leadCall?.probUp)}</p>
              </div>
              <div className="rounded-2xl border border-border/30 bg-black/20 px-4 py-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">Confidence</p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {leadCall?.confidenceScore != null ? `${Math.round(leadCall.confidenceScore)}/100` : '—'}
                </p>
              </div>
            </div>

            <div className="mt-6 rounded-2xl border border-border/30 bg-black/20 px-4 py-4">
              <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">Why this call</p>
              <p className="mt-2 text-sm leading-relaxed text-text">
                {error instanceof Error
                  ? error.message
                  : isLoading
                    ? 'Building the latest roundtable snapshot…'
                    : leadCall?.rationaleSummary ?? 'Committee rationale is still loading.'}
              </p>
            </div>
          </div>

          <div className="grid gap-4">
            <SectionCard
              title="Committee deck"
              description="Roundtable stance, calibration, and seat visibility."
              variant="surface"
              className="h-full"
            >
              <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
                <div className="rounded-2xl border border-border/30 bg-surface-muted/20 px-4 py-4">
                  <div className="flex items-center gap-2 text-text-muted">
                    <Radar className="h-4 w-4" />
                    <span className="text-[10px] uppercase tracking-[0.16em]">Direction hit rate</span>
                  </div>
                  <p className="mt-2 text-2xl font-semibold text-text">
                    {data?.scorecard?.directionHitRate != null
                      ? `${Math.round(data.scorecard.directionHitRate * 100)}%`
                      : '—'}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/30 bg-surface-muted/20 px-4 py-4">
                  <div className="flex items-center gap-2 text-text-muted">
                    <Gauge className="h-4 w-4" />
                    <span className="text-[10px] uppercase tracking-[0.16em]">Move MAE</span>
                  </div>
                  <p className="mt-2 text-2xl font-semibold text-text">
                    {formatPercent(data?.scorecard?.moveMaePct)}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/30 bg-surface-muted/20 px-4 py-4">
                  <div className="flex items-center gap-2 text-text-muted">
                    <BrainCircuit className="h-4 w-4" />
                    <span className="text-[10px] uppercase tracking-[0.16em]">Brier score</span>
                  </div>
                  <p className="mt-2 text-2xl font-semibold text-text">
                    {data?.scorecard?.brierScore != null ? data.scorecard.brierScore.toFixed(2) : '—'}
                  </p>
                </div>
              </div>
              <p className="mt-4 text-xs text-text-muted">
                {data?.scorecard?.sampleSize != null
                  ? `Scored on ${data.scorecard.sampleSize} matured committee calls.`
                  : 'Waiting for enough matured predictions to calibrate the scorecard.'}
              </p>
            </SectionCard>
          </div>
        </div>
      </SectionCard>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <SectionCard
          title="Sector board"
          description="SPDR sector ETF stance for the selected horizon."
          variant="surface"
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {sectorCalls.map((call) => {
              const Icon = directionIcon(call.directionLabel)
              return (
                <div
                  key={call.symbol}
                  className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-lg font-semibold text-text">{call.symbol}</p>
                      <p className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
                        {call.directionLabel}
                      </p>
                    </div>
                    <div className={cn('rounded-xl border p-2', directionTone(call.directionLabel))}>
                      <Icon className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="mt-4 flex items-end justify-between gap-4 text-sm">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-text-muted">Move</p>
                      <p className="mt-1 text-base font-medium text-text">{formatPercent(call.expectedMovePct)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-text-muted">Prob up</p>
                      <p className="mt-1 text-base font-medium text-text">{formatProbability(call.probUp)}</p>
                    </div>
                  </div>
                  <p className="mt-4 text-xs leading-relaxed text-text-muted">
                    {call.rationaleSummary ?? 'Committee commentary pending.'}
                  </p>
                </div>
              )
            })}
          </div>
        </SectionCard>

        <div className="grid gap-4">
          <SectionCard
            title="Source attribution"
            description="What drove the lead SPY call."
            variant="surface"
          >
            <div className="space-y-3">
              {sourceRows.map((cluster) => (
                <div
                  key={cluster.cluster}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-border/30 bg-surface-muted/20 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium uppercase tracking-[0.16em] text-text">
                      {cluster.cluster.replace(/_/g, ' ')}
                    </p>
                    {'weight' in cluster && cluster.weight != null ? (
                      <p className="text-xs text-text-muted">Weight {Math.round((cluster.weight ?? 0) * 100)}%</p>
                    ) : null}
                  </div>
                  <Badge variant="outline">{cluster.freshness ?? 'tracked'}</Badge>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            title="Seat views"
            description="Current SPY roundtable commentary."
            variant="surface"
          >
            <div className="space-y-3">
              {leadVotes.length === 0 ? (
                <p className="text-sm text-text-muted">Seat-level votes will appear after the next roundtable response.</p>
              ) : (
                leadVotes.map((vote) => (
                  <div
                    key={`${vote.seatKey}-${vote.symbol}`}
                    className="rounded-2xl border border-border/30 bg-surface-muted/20 px-4 py-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-text">{vote.seatKey}</p>
                        <p className="text-xs uppercase tracking-[0.16em] text-text-muted">
                          {vote.modelId ?? vote.agentSlug}
                        </p>
                      </div>
                      <Badge variant="outline">{vote.directionLabel}</Badge>
                    </div>
                    <p className="mt-2 text-sm text-text">{vote.rationaleSummary ?? 'No seat commentary.'}</p>
                  </div>
                ))
              )}
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  )
}
