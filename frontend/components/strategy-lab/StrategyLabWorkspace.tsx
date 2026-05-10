'use client'

import {
  AlertCircle,
  ArrowUpRight,
  Calendar,
  CheckCircle2,
  Clock,
  Crosshair,
  ExternalLink,
  Flame,
  Gauge,
  Layers,
  PlusCircle,
  RefreshCw,
  Shield,
  Sparkles,
  Star,
  Target,
  TrendingDown,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react'
import Link from 'next/link'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { AddSymbolModal } from '@/components/watchlist/AddSymbolModal'
import type {
  StrategyLabAction,
  StrategyLabBacktestPoint,
  StrategyLabBacktestSnapshot,
  StrategyLabDecisionAction,
  StrategyLabDetail,
  StrategyLabDiscoveryItem,
  StrategyLabListItem,
  StrategyLabReviewError,
  StrategyLabReviewSuccess,
  StrategyLabSignalSnapshot,
  StrategyLabSignalStatus,
} from '@/lib/api/strategy-lab'
import { formatCurrency, formatPercent } from '@/lib/formatters'
import {
  useStrategyLabDecision,
  useStrategyLabDetail,
  useStrategyLabList,
  useStrategyLabReview,
} from '@/lib/hooks/useStrategyLab'
import { useWatchlist } from '@/lib/hooks/useWatchlist'
import { cn } from '@/lib/utils'

const ACTION_LABEL: Record<StrategyLabAction, string> = {
  buy_now: 'Buy now',
  buy_in_stages: 'Buy in stages',
  hold: 'Hold',
  wait: 'Wait',
}

const ACTION_GROUPS: { key: StrategyLabAction; label: string; tone: string }[] =
  [
    { key: 'buy_now', label: 'Buy now', tone: 'text-gain' },
    { key: 'buy_in_stages', label: 'Buy in stages', tone: 'text-accent' },
    { key: 'hold', label: 'Hold', tone: 'text-text' },
    { key: 'wait', label: 'Wait', tone: 'text-text-muted' },
  ]

const SIGNAL_STATUS_LABEL: Record<StrategyLabSignalStatus, string> = {
  valid: 'Valid entry',
  better_entry: 'Better entry',
  caution: 'Caution',
  invalidated: 'Invalidated',
}

const SIGNAL_STATUS_TONE: Record<StrategyLabSignalStatus, string> = {
  valid: 'border-gain/40 bg-gain/10 text-gain',
  better_entry: 'border-accent/40 bg-accent/10 text-accent',
  caution: 'border-warning/40 bg-warning/10 text-warning',
  invalidated: 'border-loss/40 bg-loss/10 text-loss',
}

const VALIDATION_LABEL = {
  thesis: 'Thesis-validated',
  backtest: 'Backtest-validated',
  both: 'Thesis + backtest',
} as const

const ADVANCE_DELAY_MS = 1500

function isReviewError(
  value: StrategyLabReviewSuccess | StrategyLabReviewError,
): value is StrategyLabReviewError {
  return 'status' in value
}

function strategyTemplateLabel(template: string) {
  return template === 'pullback_accumulator'
    ? 'Pullback Accumulator'
    : 'Breakout Confirmation'
}

function actionTone(action: StrategyLabAction): string {
  if (action === 'buy_now') return 'text-gain'
  if (action === 'buy_in_stages') return 'text-accent'
  if (action === 'hold') return 'text-text'
  return 'text-text-muted'
}

function actionDot(action: StrategyLabAction): string {
  if (action === 'buy_now') return 'bg-gain'
  if (action === 'buy_in_stages') return 'bg-accent'
  if (action === 'hold') return 'bg-primary/60'
  return 'bg-border'
}

function unavailableDetail(item: {
  requestedStartDate: string | null
  requestedEndDate: string | null
  availableStartDate: string | null
  availableEndDate: string | null
  lookbackDays: number | null
}) {
  const requested =
    item.requestedStartDate && item.requestedEndDate
      ? `Requested ${item.requestedStartDate} → ${item.requestedEndDate}.`
      : null
  const available =
    item.availableStartDate && item.availableEndDate
      ? `Available ${item.availableStartDate} → ${item.availableEndDate}.`
      : null
  const lookback =
    item.lookbackDays != null ? `${item.lookbackDays} bars on file.` : null
  return [requested, available, lookback].filter(Boolean).join(' ')
}

function StrengthMeter({ value }: { value: number }) {
  const segments = Array.from({ length: 10 }, (_, i) => i + 1)
  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-[3px]">
        {segments.map((seg) => (
          <span
            key={seg}
            className={cn(
              'h-3 w-1.5 rounded-[1px] transition-colors',
              seg <= value
                ? seg <= 4
                  ? 'bg-warning/70'
                  : seg <= 7
                    ? 'bg-accent/80'
                    : 'bg-gain'
                : 'bg-border/40',
            )}
          />
        ))}
      </div>
      <span className="font-mono text-xs tabular-nums text-text-muted">
        {value}/10
      </span>
    </div>
  )
}

function SignalChip({ status }: { status: StrategyLabSignalStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.16em]',
        SIGNAL_STATUS_TONE[status],
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {SIGNAL_STATUS_LABEL[status]}
    </span>
  )
}

function SidebarRow({
  item,
  active,
  onSelect,
}: {
  item: StrategyLabListItem
  active: boolean
  onSelect: () => void
}) {
  const signal = item.signal
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'group block w-full rounded-xl border px-3.5 py-3 text-left transition-all',
        active
          ? 'border-primary/60 bg-primary/[0.08] shadow-[0_0_24px_-12px] shadow-primary/40'
          : 'border-border/30 bg-surface/40 hover:border-border/60 hover:bg-surface/60',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={cn('h-1.5 w-1.5 rounded-full', actionDot(item.action))}
          />
          <span className="font-mono text-[13px] font-semibold tracking-tight text-text">
            {item.symbol}
          </span>
        </div>
        {signal ? (
          <span className="font-mono text-[11px] tabular-nums text-text-muted">
            {signal.signalStrength}/10
          </span>
        ) : null}
      </div>
      <div className="mt-1.5 flex items-baseline justify-between gap-2">
        <span
          className={cn(
            'font-display italic text-[15px] leading-tight',
            actionTone(item.action),
          )}
        >
          {ACTION_LABEL[item.action]}
        </span>
        {item.primaryAccountTarget ? (
          <span className="truncate text-[10.5px] uppercase tracking-[0.14em] text-text-muted">
            {item.primaryAccountTarget.accountType}
          </span>
        ) : null}
      </div>
      {signal ? (
        <p className="mt-1 truncate text-[11.5px] text-text-muted">
          {signal.strategyName}
        </p>
      ) : item.helperText ? (
        <p className="mt-1 truncate text-[11.5px] text-warning">
          {item.helperText}
        </p>
      ) : null}
    </button>
  )
}

function chartTickStyle() {
  return {
    fontSize: 11,
    fontFamily: 'var(--font-mono, ui-monospace, monospace)',
  }
}

interface MergedChartPoint {
  date: string
  strategy: number
  buyHold: number | null
}

function mergeCurves(
  strategy: StrategyLabBacktestPoint[],
  buyHold: StrategyLabBacktestPoint[],
): MergedChartPoint[] {
  const buyHoldByDate = new Map(buyHold.map((p) => [p.date, p.equity]))
  return strategy.map((p) => ({
    date: p.date,
    strategy: p.equity,
    buyHold: buyHoldByDate.get(p.date) ?? null,
  }))
}

function ProofChart({ snapshot }: { snapshot: StrategyLabBacktestSnapshot }) {
  const merged = useMemo(
    () => mergeCurves(snapshot.equityCurve, snapshot.buyHoldCurve),
    [snapshot.equityCurve, snapshot.buyHoldCurve],
  )
  if (snapshot.status !== 'ready' || merged.length < 2) {
    return (
      <p className="text-sm text-text-muted">
        {snapshot.helperText ?? 'Backtest is not available right now.'}
      </p>
    )
  }
  return (
    <>
      <div className="grid gap-3 md:grid-cols-3">
        <Stat
          label="Strategy"
          value={
            snapshot.totalReturnPct != null
              ? formatPercent(snapshot.totalReturnPct, { sign: true })
              : '—'
          }
          tone={(snapshot.totalReturnPct ?? 0) >= 0 ? 'text-gain' : 'text-loss'}
        />
        <Stat
          label="Buy & hold"
          value={
            snapshot.buyHoldReturnPct != null
              ? formatPercent(snapshot.buyHoldReturnPct, { sign: true })
              : '—'
          }
          tone="text-text-muted"
        />
        <Stat
          label="Excess vs B&H"
          value={
            snapshot.excessReturnPct != null
              ? formatPercent(snapshot.excessReturnPct, { sign: true })
              : '—'
          }
          tone={
            (snapshot.excessReturnPct ?? 0) >= 0 ? 'text-gain' : 'text-loss'
          }
        />
      </div>
      <div className="mt-4 h-[240px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={merged}
            margin={{ top: 4, right: 12, left: 0, bottom: 4 }}
          >
            <CartesianGrid
              stroke="var(--border)"
              strokeOpacity={0.25}
              vertical={false}
            />
            <XAxis
              dataKey="date"
              stroke="var(--text-muted)"
              tick={chartTickStyle()}
              tickLine={false}
              axisLine={false}
              minTickGap={36}
            />
            <YAxis
              stroke="var(--text-muted)"
              tick={chartTickStyle()}
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={(v) =>
                typeof v === 'number'
                  ? v >= 1000
                    ? `${(v / 1000).toFixed(0)}k`
                    : v.toFixed(0)
                  : `${v}`
              }
            />
            <Tooltip
              cursor={{ stroke: 'var(--border)', strokeOpacity: 0.4 }}
              contentStyle={{
                background: 'var(--surface-elev)',
                border: '1px solid var(--border)',
                borderRadius: 12,
                fontSize: 12,
                color: 'var(--text)',
              }}
              formatter={(v) => (typeof v === 'number' ? formatCurrency(v) : v)}
            />
            <Line
              type="monotone"
              dataKey="buyHold"
              stroke="var(--text-muted)"
              strokeOpacity={0.7}
              strokeDasharray="4 4"
              dot={false}
              strokeWidth={1.5}
              isAnimationActive={false}
              name="Buy & hold"
            />
            <Line
              type="monotone"
              dataKey="strategy"
              stroke="var(--primary)"
              dot={false}
              strokeWidth={2}
              isAnimationActive={false}
              name="Strategy"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full bg-primary" />
          Strategy
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full bg-text-muted/70" />
          Buy & hold
        </span>
        <span>
          {snapshot.tradeCount} trades · {snapshot.lookbackDays ?? 0} bars
        </span>
        {snapshot.maxDrawdownPct != null ? (
          <span>
            Max drawdown{' '}
            <span className="font-mono text-text">
              {formatPercent(snapshot.maxDrawdownPct)}
            </span>
          </span>
        ) : null}
      </div>
    </>
  )
}

function ProofHero({
  symbol,
  signal,
  snapshot,
  templateLabel,
}: {
  symbol: string
  signal: StrategyLabSignalSnapshot | null
  snapshot: StrategyLabBacktestSnapshot
  templateLabel: string
}) {
  return (
    <SectionCard
      variant="surface"
      title={
        <span className="inline-flex items-center gap-2">
          <Layers className="h-4 w-4 text-primary" />
          Proof
        </span>
      }
      description={
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-text-muted">
          <span className="font-mono text-[13px] font-semibold uppercase tracking-[0.18em] text-text">
            {symbol}
          </span>
          {signal ? <SignalChip status={signal.signalStatus} /> : null}
          {signal ? (
            <span className="text-[11px] uppercase tracking-[0.14em]">
              {VALIDATION_LABEL[signal.validationType]}
            </span>
          ) : null}
          <span className="text-text-muted/80">{templateLabel}</span>
          {signal?.strategyName ? (
            <span className="text-text-muted/80">· {signal.strategyName}</span>
          ) : null}
        </span>
      }
    >
      <ProofChart snapshot={snapshot} />
    </SectionCard>
  )
}

function CallSummary({ detail }: { detail: StrategyLabDetail }) {
  const account = detail.primaryAccountTarget
  const ticket = detail.ticket
  const signal = detail.signal
  return (
    <SectionCard variant="surface" contentClassName="px-6 py-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
              Call
            </span>
            {signal ? (
              <span className="text-[11px] uppercase tracking-[0.14em] text-text-muted">
                strength {signal.signalStrength}/10
              </span>
            ) : null}
          </div>
          <h2
            className={cn(
              'font-display italic text-[clamp(1.5rem,3vw,2.25rem)] leading-tight tracking-tight',
              actionTone(detail.action),
            )}
          >
            {ACTION_LABEL[detail.action]}
          </h2>
          {detail.helperText ? (
            <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-[12px] text-warning">
              {detail.helperText}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-muted">
            <span className="inline-flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              Updated <RelativeTime value={detail.updatedAt} />
            </span>
            {signal ? (
              <span className="inline-flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                Signal {signal.signalDate}
              </span>
            ) : null}
            {signal?.expectedSharpe != null ? (
              <span>
                Expected Sharpe{' '}
                <span className="font-mono text-text">
                  {signal.expectedSharpe.toFixed(2)}
                </span>
              </span>
            ) : null}
          </div>
        </div>
        {ticket ? (
          <div className="min-w-[220px] rounded-2xl border border-primary/30 bg-primary/[0.06] px-4 py-4">
            <p className="text-[10.5px] uppercase tracking-[0.18em] text-text-muted">
              First tranche
            </p>
            <p className="mt-1 font-display italic text-3xl text-text">
              {formatCurrency(ticket.firstTrancheDollars)}
            </p>
            <p className="mt-0.5 font-mono text-[12px] tabular-nums text-text-muted">
              ≈ {ticket.estimatedShares.toFixed(2)} shares
            </p>
            <div className="mt-3 border-t border-border/40 pt-3 text-[11.5px]">
              <p className="text-text-muted">Account</p>
              <p className="mt-0.5 font-medium text-text">
                {ticket.accountName}
              </p>
              {account ? (
                <p className="mt-0.5 font-mono text-text-muted">
                  Cash {formatCurrency(account.cashBalance)}
                </p>
              ) : null}
            </div>
          </div>
        ) : account ? (
          <div className="min-w-[200px] rounded-2xl border border-border/40 bg-surface/40 px-4 py-4">
            <p className="text-[10.5px] uppercase tracking-[0.18em] text-text-muted">
              Account context
            </p>
            <p className="mt-2 font-display italic text-xl text-text">
              {account.accountName}
            </p>
            <p className="mt-1 font-mono text-[12px] text-text-muted">
              Cash {formatCurrency(account.cashBalance)}
            </p>
            {account.heldMarketValue != null ? (
              <p className="mt-0.5 font-mono text-[12px] text-text-muted">
                Held {formatCurrency(account.heldMarketValue)}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </SectionCard>
  )
}

function SignalCard({ detail }: { detail: StrategyLabDetail }) {
  const signal = detail.signal
  if (!signal) {
    return (
      <SectionCard variant="surface" title="Signal">
        <p className="text-sm text-text-muted">
          No fresh signal from any active strategy. Strategy Lab will surface a
          call as soon as one fires.
        </p>
      </SectionCard>
    )
  }
  return (
    <SectionCard
      variant="surface"
      title={
        <span className="inline-flex items-center gap-2">
          <Flame className="h-4 w-4 text-accent" />
          Signal
        </span>
      }
      description={`${signal.strategyName} · strength ${signal.signalStrength}/10`}
    >
      <div className="space-y-5">
        <div className="space-y-2">
          <p className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
            Strength
          </p>
          <StrengthMeter value={signal.signalStrength} />
        </div>
        {signal.signalReasons.length > 0 ? (
          <div className="space-y-2">
            <p className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
              Why now
            </p>
            <div className="flex flex-wrap gap-1.5">
              {signal.signalReasons.map((reason) => (
                <span
                  key={reason}
                  className="rounded-full border border-border/40 bg-surface-muted/30 px-3 py-1 text-[11.5px] text-text"
                >
                  {reason}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        <div className="space-y-2 border-t border-border/30 pt-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
            What Strategy Lab is reading
          </p>
          <ul className="space-y-1.5 text-[13px] leading-relaxed text-text-muted">
            {detail.whyBullets.map((bullet) => (
              <li key={bullet} className="flex gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-accent" />
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="rounded-lg border border-border/40 bg-surface-muted/20 px-3 py-2 text-[12.5px] text-text">
          {detail.watchItem}
        </p>
      </div>
    </SectionCard>
  )
}

function RiskCard({ signal }: { signal: StrategyLabSignalSnapshot | null }) {
  if (!signal) return null
  const risk = signal.risk
  const distanceToStop =
    risk.entryPrice > 0
      ? ((risk.stopLoss - risk.currentPrice) / risk.currentPrice) * 100
      : 0
  const distanceToTarget =
    risk.entryPrice > 0
      ? ((risk.targetPrice - risk.currentPrice) / risk.currentPrice) * 100
      : 0
  return (
    <SectionCard
      variant="surface"
      title={
        <span className="inline-flex items-center gap-2">
          <Crosshair className="h-4 w-4 text-warning" />
          Risk frame
        </span>
      }
      description="Live tape vs strategy-supplied stop and target."
    >
      <div className="grid gap-3 md:grid-cols-4">
        <RiskCell
          label="Entry"
          value={formatCurrency(risk.entryPrice)}
          icon={<Target className="h-3.5 w-3.5" />}
          tone="text-text"
        />
        <RiskCell
          label="Now"
          value={formatCurrency(risk.currentPrice)}
          icon={
            risk.priceChangePct >= 0 ? (
              <TrendingUp className="h-3.5 w-3.5 text-gain" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5 text-loss" />
            )
          }
          sub={formatPercent(risk.priceChangePct, { sign: true })}
          subTone={risk.priceChangePct >= 0 ? 'text-gain' : 'text-loss'}
        />
        <RiskCell
          label="Stop"
          value={formatCurrency(risk.stopLoss)}
          icon={<Shield className="h-3.5 w-3.5 text-loss" />}
          sub={`${distanceToStop.toFixed(1)}% away`}
          subTone="text-text-muted"
        />
        <RiskCell
          label="Target"
          value={formatCurrency(risk.targetPrice)}
          icon={<Sparkles className="h-3.5 w-3.5 text-gain" />}
          sub={`+${distanceToTarget.toFixed(1)}% upside`}
          subTone="text-text-muted"
        />
      </div>
      <div className="mt-4 flex items-center justify-between rounded-xl border border-border/40 bg-surface-muted/20 px-3.5 py-2.5">
        <span className="inline-flex items-center gap-2 text-[12px] text-text-muted">
          <Gauge className="h-3.5 w-3.5" />
          Risk / reward
        </span>
        <span className="font-mono text-[14px] tabular-nums text-text">
          {risk.riskRewardRatio.toFixed(2)} : 1
        </span>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11.5px] text-text-muted">
        <span>
          Suggested size{' '}
          <span className="font-mono text-text">
            {formatCurrency(signal.suggestedSizeDollars)}
          </span>{' '}
          ·{' '}
          <span className="font-mono text-text">
            {signal.suggestedSizeShares}
          </span>{' '}
          shares
        </span>
      </div>
    </SectionCard>
  )
}

function RiskCell({
  label,
  value,
  sub,
  subTone,
  icon,
  tone,
}: {
  label: string
  value: string
  sub?: string
  subTone?: string
  icon?: React.ReactNode
  tone?: string
}) {
  return (
    <div className="rounded-xl border border-border/40 bg-surface/40 px-3.5 py-3">
      <div className="flex items-center justify-between text-[10.5px] uppercase tracking-[0.16em] text-text-muted">
        <span>{label}</span>
        {icon}
      </div>
      <p
        className={cn(
          'mt-1.5 font-mono text-base tabular-nums',
          tone ?? 'text-text',
        )}
      >
        {value}
      </p>
      {sub ? (
        <p
          className={cn('mt-0.5 font-mono text-[11.5px] tabular-nums', subTone)}
        >
          {sub}
        </p>
      ) : null}
    </div>
  )
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: string
}) {
  return (
    <div className="rounded-xl border border-border/40 bg-surface/40 px-3.5 py-3">
      <p className="text-[10.5px] uppercase tracking-[0.16em] text-text-muted">
        {label}
      </p>
      <p
        className={cn(
          'mt-1 font-display italic text-2xl leading-tight tabular-nums',
          tone ?? 'text-text',
        )}
      >
        {value}
      </p>
    </div>
  )
}

function ReviewBlock({
  detail,
  result,
  onRequest,
  isPending,
}: {
  detail: StrategyLabDetail
  result: StrategyLabReviewSuccess | StrategyLabReviewError | null
  onRequest: () => void
  isPending: boolean
}) {
  if (!detail.review.available) {
    return (
      <SectionCard
        variant="surface"
        title={
          <span className="inline-flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-text-muted" />
            AI review
          </span>
        }
      >
        <p className="text-sm text-text-muted">{detail.review.message}</p>
      </SectionCard>
    )
  }
  return (
    <SectionCard
      variant="surface"
      title={
        <span className="inline-flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-accent" />
          AI review
        </span>
      }
      description="Optional one-shot memo from the equity-analyst agent."
      actions={
        <Button
          size="sm"
          variant="outline"
          onClick={onRequest}
          disabled={isPending}
        >
          {isPending
            ? 'Reviewing…'
            : result && !isReviewError(result)
              ? 'Re-run review'
              : 'Run review'}
        </Button>
      }
    >
      {!result ? (
        <p className="text-sm text-text-muted">
          The agent will weigh tailwinds, headwinds, and what would invalidate
          the call.
        </p>
      ) : isReviewError(result) ? (
        <p className="text-sm text-warning">{result.message}</p>
      ) : (
        <div className="space-y-4">
          <div className="space-y-1">
            <p className="font-display italic text-2xl text-text">
              {result.verdict}
            </p>
            <p className="text-[13px] leading-relaxed text-text-muted">
              {result.summary}
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <ReviewList
              label="Tailwinds"
              tone="text-gain"
              items={result.tailwinds}
            />
            <ReviewList
              label="Headwinds"
              tone="text-loss"
              items={result.headwinds}
            />
          </div>
          {result.invalidationTriggers.length > 0 ? (
            <ReviewList
              label="Invalidation triggers"
              tone="text-warning"
              items={result.invalidationTriggers}
            />
          ) : null}
          <div className="rounded-xl border border-primary/30 bg-primary/[0.06] px-3.5 py-3">
            <p className="text-[10.5px] uppercase tracking-[0.18em] text-text-muted">
              Act now or wait
            </p>
            <p className="mt-1 text-[13px] leading-relaxed text-text">
              {result.actNowOrWait}
            </p>
          </div>
        </div>
      )}
    </SectionCard>
  )
}

function ReviewList({
  label,
  items,
  tone,
}: {
  label: string
  items: string[]
  tone: string
}) {
  if (items.length === 0) {
    return (
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
          {label}
        </p>
        <p className="mt-1 text-[12.5px] text-text-muted/80">None named.</p>
      </div>
    )
  }
  return (
    <div>
      <p className={cn('text-[11px] uppercase tracking-[0.16em]', tone)}>
        {label}
      </p>
      <ul className="mt-1 space-y-1 text-[13px] leading-relaxed text-text-muted">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span
              className={cn(
                'mt-1.5 h-1 w-1 shrink-0 rounded-full',
                tone.replace('text-', 'bg-'),
              )}
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function DecisionBar({
  detail,
  onDecide,
  pending,
  lastResult,
}: {
  detail: StrategyLabDetail
  onDecide: (action: StrategyLabDecisionAction) => void
  pending: StrategyLabDecisionAction | null
  lastResult: {
    action: StrategyLabDecisionAction
    nextStep: string | null
  } | null
}) {
  const canAct =
    detail.action === 'buy_now' || detail.action === 'buy_in_stages'
  return (
    <SectionCard
      variant="surface"
      title={
        <span className="inline-flex items-center gap-2">
          <Zap className="h-4 w-4 text-primary" />
          Decision
        </span>
      }
      description="Logged through the symbol workflow — auditable and dismissable from Today."
    >
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          onClick={() => onDecide('act_now')}
          disabled={!canAct || pending !== null}
        >
          {pending === 'act_now' ? 'Logging…' : 'Act now'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onDecide('stage')}
          disabled={!canAct || pending !== null}
        >
          {pending === 'stage' ? 'Logging…' : 'Stage buy'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onDecide('snooze')}
          disabled={pending !== null}
        >
          {pending === 'snooze' ? 'Logging…' : 'Snooze 24h'}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onDecide('dismiss')}
          disabled={pending !== null}
          className="text-loss hover:text-loss"
        >
          {pending === 'dismiss' ? 'Logging…' : 'Dismiss'}
        </Button>
      </div>
      {lastResult ? (
        <div className="mt-3 inline-flex items-start gap-2 rounded-lg border border-gain/30 bg-gain/[0.08] px-3 py-2 text-[12.5px] text-text">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-gain" />
          <span>
            <span className="font-medium">
              {lastResult.action.replace('_', ' ')}
            </span>
            {' — '}
            {lastResult.nextStep}
          </span>
        </div>
      ) : null}
    </SectionCard>
  )
}

function DiscoveryHeroCard({
  discovery,
  onTrack,
}: {
  discovery: StrategyLabDiscoveryItem
  onTrack: (symbol: string) => void
}) {
  const snapshot = discovery.backtestSnapshot ?? null
  const templateLabel = strategyTemplateLabel(
    discovery.strategyType.toLowerCase().includes('breakout') ||
      discovery.strategyType.toLowerCase().includes('momentum')
      ? 'breakout_confirmation'
      : 'pullback_accumulator',
  )
  return (
    <SectionCard variant="surface" contentClassName="px-6 py-6">
      <div className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[13px] font-semibold uppercase tracking-[0.18em] text-text">
                {discovery.symbol}
              </span>
              <SignalChip status={discovery.signalStatus} />
              <span className="text-[11px] uppercase tracking-[0.14em] text-text-muted">
                {VALIDATION_LABEL[discovery.validationType]}
              </span>
            </div>
            <p className="text-[13px] text-text-muted">
              {discovery.strategyName} · {templateLabel}
              {discovery.expectedSharpe != null ? (
                <>
                  <span className="text-text-muted/60"> · </span>
                  Expected Sharpe{' '}
                  <span className="font-mono text-text">
                    {discovery.expectedSharpe.toFixed(2)}
                  </span>
                </>
              ) : null}
            </p>
            <StrengthMeter value={discovery.signalStrength} />
          </div>
          <Button
            size="sm"
            onClick={() => onTrack(discovery.symbol)}
            className="shrink-0"
          >
            <PlusCircle className="mr-2 h-4 w-4" />
            Track {discovery.symbol}
          </Button>
        </div>
        {snapshot ? (
          <div className="border-t border-border/40 pt-5">
            <p className="mb-3 text-[11px] uppercase tracking-[0.18em] text-text-muted">
              Walk-forward proof
            </p>
            <ProofChart snapshot={snapshot} />
          </div>
        ) : (
          <div className="rounded-xl border border-border/40 bg-surface-muted/20 px-3.5 py-3 text-[12.5px] text-text-muted">
            Backtest snapshot is being prepared. Track this symbol to compute
            its full proof curve in the detail view.
          </div>
        )}
        <div className="rounded-xl border border-border/40 bg-surface-muted/20 px-3.5 py-3 text-[12.5px] text-text-muted">
          Track <span className="font-mono text-text">{discovery.symbol}</span>{' '}
          to bring it into your universe — Strategy Lab then sizes the first
          tranche against your accounts and lets you log a decision.
        </div>
      </div>
    </SectionCard>
  )
}

function DiscoveryTile({
  discovery,
  onTrack,
}: {
  discovery: StrategyLabDiscoveryItem
  onTrack: (symbol: string) => void
}) {
  return (
    <div className="rounded-xl border border-border/40 bg-surface/40 px-3.5 py-3 transition-colors hover:border-accent/40">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[13px] font-semibold tracking-tight text-text">
          {discovery.symbol}
        </span>
        <SignalChip status={discovery.signalStatus} />
      </div>
      <p className="mt-1.5 truncate text-[12px] text-text-muted">
        {discovery.strategyName} · {discovery.strategyType}
      </p>
      <div className="mt-2.5">
        <StrengthMeter value={discovery.signalStrength} />
      </div>
      <div className="mt-2.5 grid grid-cols-3 gap-2 text-[11px] text-text-muted">
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em]">Stop</p>
          <p className="font-mono tabular-nums text-text">
            {formatCurrency(discovery.risk.stopLoss)}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em]">Target</p>
          <p className="font-mono tabular-nums text-text">
            {formatCurrency(discovery.risk.targetPrice)}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em]">RR</p>
          <p className="font-mono tabular-nums text-text">
            {discovery.risk.riskRewardRatio.toFixed(2)}
          </p>
        </div>
      </div>
      <div className="mt-3 flex justify-end">
        <Button
          size="sm"
          variant="outline"
          onClick={() => onTrack(discovery.symbol)}
        >
          Track {discovery.symbol}
        </Button>
      </div>
    </div>
  )
}

function DiscoveryTileRail({
  discoveries,
  title,
  description,
  onTrack,
}: {
  discoveries: StrategyLabDiscoveryItem[]
  title: string
  description?: string
  onTrack: (symbol: string) => void
}) {
  if (discoveries.length === 0) return null
  return (
    <SectionCard
      variant="surface"
      title={
        <span className="inline-flex items-center gap-2">
          <Star className="h-4 w-4 text-accent" />
          {title}
        </span>
      }
      description={description}
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {discoveries.map((d) => (
          <DiscoveryTile
            key={`${d.symbol}-${d.strategyName}`}
            discovery={d}
            onTrack={onTrack}
          />
        ))}
      </div>
    </SectionCard>
  )
}

function MonitoringList({ items }: { items: StrategyLabListItem[] }) {
  if (items.length === 0) return null
  return (
    <SectionCard
      variant="surface"
      title="Tracked, monitoring"
      description="Strategies are scoring these symbols continuously. A call surfaces here as soon as one passes walk-forward validation."
    >
      <ul className="space-y-2">
        {items.map((item) => (
          <li
            key={item.symbol}
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/30 bg-surface/40 px-3.5 py-2.5"
          >
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'h-1.5 w-1.5 rounded-full',
                  actionDot(item.action),
                )}
              />
              <span className="font-mono text-[13px] font-semibold tracking-tight text-text">
                {item.symbol}
              </span>
              <span className="text-[11.5px] text-text-muted">
                {strategyTemplateLabel(item.strategyTemplate)}
              </span>
            </div>
            <div className="flex items-center gap-3 text-[11.5px] text-text-muted">
              {item.backtestLookbackDays != null ? (
                <span>{item.backtestLookbackDays} bars on file</span>
              ) : null}
              {item.backtestStatus === 'ready' ? (
                <span className="text-gain">Backtest ✓</span>
              ) : item.backtestStatus === 'insufficient_history' ? (
                <span className="text-warning">History thin</span>
              ) : item.backtestStatus === 'no_trades' ? (
                <span className="text-text-muted">No trades</span>
              ) : item.backtestStatus === 'quote_unavailable' ? (
                <span className="text-warning">Quote stale</span>
              ) : null}
              <Link
                href={`/symbols/${item.symbol}`}
                className="inline-flex items-center gap-1 text-text-muted hover:text-text"
              >
                Symbol page <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </SectionCard>
  )
}

function QuietHero({ trackedCount }: { trackedCount: number }) {
  return (
    <SectionCard variant="surface" contentClassName="px-6 py-10">
      <div className="mx-auto max-w-prose space-y-3 text-center">
        <p className="font-display italic text-3xl text-text">
          Universe is quiet.
        </p>
        <p className="text-[14px] leading-relaxed text-text-muted">
          {trackedCount} symbol{trackedCount === 1 ? '' : 's'} tracked. None of
          them firing a validated call right now.
        </p>
        <p className="text-[13px] leading-relaxed text-text-muted">
          Strategies are watching. We&rsquo;ll surface the call the moment one
          passes walk-forward validation.
        </p>
      </div>
    </SectionCard>
  )
}

function ColdStartIntro({
  onAddSymbol,
  hasDiscoveries,
}: {
  onAddSymbol: () => void
  hasDiscoveries: boolean
}) {
  return (
    <SectionCard variant="surface">
      <div className="space-y-2">
        <p className="text-[13px] leading-relaxed text-text-muted">
          {hasDiscoveries ? (
            <>
              No tracked symbols yet. Below is a validated call firing in the
              wider market right now &mdash; the strategy beat or rivaled
              buy-and-hold over the lookback. Click <strong>Track</strong> to
              pull a symbol into your universe.
            </>
          ) : (
            <>
              Strategy Lab surfaces calls only after a strategy has proved
              itself on the symbol&rsquo;s own history via walk-forward
              backtest. There&rsquo;s nothing firing across the wider market
              right now &mdash; add a symbol to start tracking.
            </>
          )}
        </p>
        <div>
          <Button onClick={onAddSymbol}>
            <PlusCircle className="mr-2 h-4 w-4" />
            Add symbol
          </Button>
        </div>
      </div>
    </SectionCard>
  )
}

export function StrategyLabWorkspace({
  initialSymbol,
}: {
  initialSymbol: string | null
}) {
  const normalizedInitialSymbol = initialSymbol?.toUpperCase() ?? null
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(
    normalizedInitialSymbol,
  )
  const [reviewResult, setReviewResult] = useState<
    StrategyLabReviewSuccess | StrategyLabReviewError | null
  >(null)
  const [pendingDecision, setPendingDecision] =
    useState<StrategyLabDecisionAction | null>(null)
  const [decisionFeedback, setDecisionFeedback] = useState<{
    action: StrategyLabDecisionAction
    nextStep: string | null
  } | null>(null)
  const [addSymbolOpen, setAddSymbolOpen] = useState(false)
  const [addSymbolSeed, setAddSymbolSeed] = useState('')
  const lastAppliedInitialSymbol = useRef<string | null>(
    normalizedInitialSymbol,
  )
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const listQuery = useStrategyLabList()
  const listItems = listQuery.data?.items ?? []
  const unavailableItems = listQuery.data?.unavailableItems ?? []
  const discoveries = listQuery.data?.discoveries ?? []
  const detailQuery = useStrategyLabDetail(selectedSymbol)
  const reviewMutation = useStrategyLabReview(selectedSymbol)
  const decisionMutation = useStrategyLabDecision(selectedSymbol)
  const watchlistQuery = useWatchlist()
  const watchlistCount = watchlistQuery.data?.items.length ?? 0

  const actionableItems = useMemo(
    () => listItems.filter((item) => item.action !== 'wait'),
    [listItems],
  )
  const isQuiet = listItems.length > 0 && actionableItems.length === 0
  const isColdStart = listItems.length === 0
  const hasDiscoveries = discoveries.length > 0

  useEffect(() => {
    if (normalizedInitialSymbol !== lastAppliedInitialSymbol.current) {
      lastAppliedInitialSymbol.current = normalizedInitialSymbol
      setSelectedSymbol(normalizedInitialSymbol)
      setReviewResult(null)
      setDecisionFeedback(null)
    }
  }, [normalizedInitialSymbol])

  useEffect(() => {
    if (
      !normalizedInitialSymbol &&
      !selectedSymbol &&
      actionableItems.length > 0
    ) {
      setSelectedSymbol(actionableItems[0]?.symbol ?? null)
    }
  }, [normalizedInitialSymbol, selectedSymbol, actionableItems])

  useEffect(() => {
    return () => {
      if (advanceTimer.current) {
        clearTimeout(advanceTimer.current)
      }
    }
  }, [])

  const refreshAll = async () => {
    setReviewResult(null)
    setDecisionFeedback(null)
    await listQuery.refetch()
    if (selectedSymbol) {
      await detailQuery.refetch()
    }
  }

  const openAddSymbol = (seed = '') => {
    setAddSymbolSeed(seed)
    setAddSymbolOpen(true)
  }

  const handleAddSymbolOpenChange = (next: boolean) => {
    setAddSymbolOpen(next)
    if (!next) {
      setAddSymbolSeed('')
      void listQuery.refetch()
    }
  }

  const selectedDetail = detailQuery.data
  const staleDetached =
    selectedDetail &&
    !listItems.some((item) => item.symbol === selectedDetail.symbol)

  const listErrorMessage = listQuery.error?.message ?? null
  const detailErrorMessage = detailQuery.error?.message ?? null

  const groupedItems = useMemo(() => {
    const groups: Record<StrategyLabAction, StrategyLabListItem[]> = {
      buy_now: [],
      buy_in_stages: [],
      hold: [],
      wait: [],
    }
    for (const item of listItems) {
      groups[item.action].push(item)
    }
    return groups
  }, [listItems])

  const handleDecide = (action: StrategyLabDecisionAction) => {
    if (!selectedSymbol) return
    setPendingDecision(action)
    decisionMutation.mutate(
      { action },
      {
        onSuccess: (result) => {
          setDecisionFeedback({
            action: result.action,
            nextStep: result.nextStep,
          })
          setPendingDecision(null)
          if (advanceTimer.current) {
            clearTimeout(advanceTimer.current)
          }
          const nextItem = actionableItems.find(
            (item) => item.symbol !== selectedSymbol,
          )
          if (nextItem) {
            advanceTimer.current = setTimeout(() => {
              setSelectedSymbol(nextItem.symbol)
              setReviewResult(null)
              setDecisionFeedback(null)
              advanceTimer.current = null
            }, ADVANCE_DELAY_MS)
          }
          void listQuery.refetch()
        },
        onError: () => setPendingDecision(null),
      },
    )
  }

  const handleReview = () => {
    if (!selectedSymbol) return
    setReviewResult(null)
    reviewMutation.mutate(undefined, {
      onSuccess: (result) => setReviewResult(result),
      onError: (error) =>
        setReviewResult({ status: 'unavailable', message: error.message }),
    })
  }

  const totalsByGroup = ACTION_GROUPS.map((g) => ({
    ...g,
    count: groupedItems[g.key].length,
  }))

  const headerActions = (
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" onClick={() => void refreshAll()}>
        <RefreshCw className="mr-2 h-4 w-4" />
        Refresh
      </Button>
      <Button onClick={() => openAddSymbol()}>
        <PlusCircle className="mr-2 h-4 w-4" />
        Add symbol
      </Button>
    </div>
  )

  return (
    <PageContainer className="space-y-6 py-8">
      <PageHeader
        eyebrow="Investing · Strategy Lab"
        title="Pre-vetted calls, with the proof attached."
        description="Walk-forward backtest on every line. The strategy beat or rivaled buy-and-hold over the lookback, or it doesn't show."
        actions={headerActions}
      />

      {!listQuery.isLoading && totalsByGroup.some((g) => g.count > 0) ? (
        <div className="flex flex-wrap gap-2 text-[11.5px] uppercase tracking-[0.14em] text-text-muted">
          {totalsByGroup
            .filter((g) => g.count > 0)
            .map((g) => (
              <span
                key={g.key}
                className={cn(
                  'inline-flex items-center gap-2 rounded-full border border-border/40 bg-surface/40 px-3 py-1',
                  g.tone,
                )}
              >
                <span
                  className={cn('h-1.5 w-1.5 rounded-full', actionDot(g.key))}
                />
                {g.count} {g.label}
              </span>
            ))}
        </div>
      ) : null}

      {listQuery.isLoading ? (
        <SectionCard variant="surface">
          <div className="space-y-3">
            <div className="skeleton h-9 rounded-xl" />
            <div className="skeleton h-9 rounded-xl" />
            <div className="skeleton h-9 rounded-xl" />
          </div>
        </SectionCard>
      ) : null}

      {listErrorMessage ? (
        <SectionCard variant="surface" title="Strategy Lab">
          <div className="flex items-start gap-3 text-sm text-text-muted">
            <AlertCircle className="mt-0.5 h-4 w-4 text-warning" />
            <p>{listErrorMessage}</p>
          </div>
        </SectionCard>
      ) : null}

      {unavailableItems.length > 0 ? (
        <SectionCard variant="surface" title="Partial data">
          <div className="space-y-2">
            <div className="flex items-start gap-2 text-sm text-text-muted">
              <AlertCircle className="mt-0.5 h-4 w-4 text-warning" />
              <p>
                {`${unavailableItems.length} symbol${unavailableItems.length === 1 ? '' : 's'} ${unavailableItems.length === 1 ? 'needs' : 'need'} more data before Strategy Lab can score the backtest.`}
              </p>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              {unavailableItems.map((item) => (
                <div
                  key={`${item.symbol}-${item.reason}`}
                  className="rounded-xl border border-warning/20 bg-warning/[0.06] px-3 py-2.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[13px] font-semibold text-text">
                      {item.symbol}
                    </span>
                    <span className="text-[10px] uppercase tracking-[0.14em] text-warning">
                      {item.reason === 'insufficient_history'
                        ? 'History'
                        : 'Unavailable'}
                    </span>
                  </div>
                  <p className="mt-1 text-[12.5px] text-text-muted">
                    {item.message}
                  </p>
                  {unavailableDetail(item) ? (
                    <p className="mt-1 text-[11px] text-text-muted/80">
                      {unavailableDetail(item)}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        </SectionCard>
      ) : null}

      {!listQuery.isLoading && !listErrorMessage && isColdStart ? (
        <>
          <ColdStartIntro
            onAddSymbol={() => openAddSymbol()}
            hasDiscoveries={hasDiscoveries}
          />
          {hasDiscoveries ? (
            <DiscoveryHeroCard
              discovery={discoveries[0]}
              onTrack={(symbol) => openAddSymbol(symbol)}
            />
          ) : null}
          {discoveries.length > 1 ? (
            <DiscoveryTileRail
              discoveries={discoveries.slice(1)}
              title="Next validated calls"
              description="Click Track to pull any of these into your universe."
              onTrack={(symbol) => openAddSymbol(symbol)}
            />
          ) : null}
        </>
      ) : null}

      {!listQuery.isLoading && !listErrorMessage && isQuiet ? (
        <>
          <QuietHero trackedCount={listItems.length} />
          <MonitoringList items={listItems} />
          <DiscoveryTileRail
            discoveries={discoveries}
            title="Next-strongest outside your universe"
            description="Calls firing on symbols you don't track yet. Track to pull them in."
            onTrack={(symbol) => openAddSymbol(symbol)}
          />
        </>
      ) : null}

      {!listQuery.isLoading &&
      !listErrorMessage &&
      actionableItems.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <SectionCard
            variant="surface"
            title="Universe"
            description={`${listItems.length} symbol${listItems.length === 1 ? '' : 's'} in scope`}
            padding="sm"
            contentClassName="px-3 pb-3"
          >
            <div className="space-y-4">
              {ACTION_GROUPS.map((group) => {
                const items = groupedItems[group.key]
                if (items.length === 0) return null
                return (
                  <div key={group.key} className="space-y-1.5">
                    <div className="flex items-center justify-between px-1">
                      <p
                        className={cn(
                          'text-[10.5px] uppercase tracking-[0.18em]',
                          group.tone,
                        )}
                      >
                        {group.label}
                      </p>
                      <span className="font-mono text-[10.5px] text-text-muted">
                        {items.length}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {items.map((item) => (
                        <SidebarRow
                          key={item.symbol}
                          item={item}
                          active={item.symbol === selectedSymbol}
                          onSelect={() => {
                            if (advanceTimer.current) {
                              clearTimeout(advanceTimer.current)
                              advanceTimer.current = null
                            }
                            setSelectedSymbol(item.symbol)
                            setReviewResult(null)
                            setDecisionFeedback(null)
                          }}
                        />
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </SectionCard>

          <div className="space-y-4">
            {selectedDetail ? (
              <div className="flex items-center justify-end">
                <Link
                  href={`/symbols/${selectedDetail.symbol}`}
                  className="inline-flex items-center gap-1.5 text-[11.5px] text-text-muted hover:text-text"
                >
                  See full symbol page
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            ) : null}

            {staleDetached ? (
              <div className="rounded-xl border border-warning/30 bg-warning/[0.08] px-3.5 py-2.5 text-[12.5px] text-warning">
                <span className="inline-flex items-center gap-2">
                  <X className="h-3.5 w-3.5" />
                  This symbol left the fresh list — showing its stale detail
                  below.
                </span>
              </div>
            ) : null}

            {detailErrorMessage ? (
              <SectionCard variant="surface" title="Strategy Lab detail">
                <div className="flex items-start gap-3 text-sm text-text-muted">
                  <AlertCircle className="mt-0.5 h-4 w-4 text-warning" />
                  <p>{detailErrorMessage}</p>
                </div>
              </SectionCard>
            ) : null}

            {selectedDetail ? (
              <>
                <ProofHero
                  symbol={selectedDetail.symbol}
                  signal={selectedDetail.signal}
                  snapshot={selectedDetail.backtestSnapshot}
                  templateLabel={strategyTemplateLabel(
                    selectedDetail.strategyTemplate,
                  )}
                />
                <CallSummary detail={selectedDetail} />
                <SignalCard detail={selectedDetail} />
                <RiskCard signal={selectedDetail.signal} />
                <ReviewBlock
                  detail={selectedDetail}
                  result={reviewResult}
                  onRequest={handleReview}
                  isPending={reviewMutation.isPending}
                />
                <DecisionBar
                  detail={selectedDetail}
                  onDecide={handleDecide}
                  pending={pendingDecision}
                  lastResult={decisionFeedback}
                />
              </>
            ) : null}
          </div>
        </div>
      ) : null}

      <AddSymbolModal
        open={addSymbolOpen}
        onOpenChange={handleAddSymbolOpenChange}
        currentCount={watchlistCount}
        initialSymbols={addSymbolSeed}
      />
    </PageContainer>
  )
}
