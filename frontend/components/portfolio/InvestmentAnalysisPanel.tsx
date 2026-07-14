'use client'

import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import Link from 'next/link'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type {
  PortfolioAnalytics,
  PositionPerformance,
} from '@/lib/api/portfolio'
import { formatCurrencyWhole, formatPercent } from '@/lib/formatters'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { cn } from '@/lib/utils'

function Metric({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail: string
}) {
  return (
    <div className="rounded-xl border border-border/40 bg-surface-muted/15 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-muted">
        {label}
      </p>
      <p className="mt-2 font-display text-2xl italic text-text tabular-nums">
        {value}
      </p>
      <p className="mt-1 text-xs leading-5 text-text-muted">{detail}</p>
    </div>
  )
}

function representedCoverage(analytics: PortfolioAnalytics): number | null {
  const householdTotal = analytics.householdInvestedTotalValue
  if (
    !analytics.householdTotalsTrusted ||
    householdTotal == null ||
    householdTotal <= 0
  ) {
    return null
  }
  return Math.min(
    100,
    Math.max(0, (analytics.cashInclusiveTotalValue / householdTotal) * 100),
  )
}

function AnalysisScope({ analytics }: { analytics: PortfolioAnalytics }) {
  const coverage = representedCoverage(analytics)

  if (!analytics.householdTotalsTrusted) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-amber-400/35 bg-amber-400/10 p-5 text-sm text-amber-100"
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
          <div className="space-y-2">
            <p className="font-semibold text-text">
              Household total is blocked pending account review
            </p>
            <p className="leading-6 text-text-muted">
              {analytics.accountControlSummary ??
                'Household account controls are unavailable, so this page will not treat the household total as trusted.'}
            </p>
            <p className="text-xs leading-5 text-text-muted">
              Risk and sector calculations below still describe the priced
              positions shown in Investing; they do not claim complete household
              coverage.
            </p>
            <Link
              href="/money?tab=accounts"
              className="inline-flex items-center gap-1 text-xs font-semibold text-warning hover:underline"
            >
              Review account control <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const partial = coverage != null && coverage < 99.5
  const ScopeIcon = partial ? AlertTriangle : CheckCircle2
  return (
    <div
      className={cn(
        'rounded-2xl border p-5 text-sm',
        partial
          ? 'border-amber-400/30 bg-amber-400/10'
          : 'border-gain/30 bg-gain/10',
      )}
    >
      <div className="flex items-start gap-3">
        <ScopeIcon
          className={cn(
            'mt-0.5 h-5 w-5 shrink-0',
            partial ? 'text-warning' : 'text-gain',
          )}
        />
        <div className="space-y-2">
          <p className="font-semibold text-text">
            {partial
              ? 'Partial household analysis'
              : 'Household totals reconciled'}
          </p>
          <p className="leading-6 text-text-muted">
            {coverage == null
              ? 'The represented share cannot be calculated because no household investment total is available.'
              : `${formatPercent(coverage)} of known household investment value is represented by accounts in this Investing workspace.`}
          </p>
          <p className="text-xs leading-5 text-text-muted">
            Sector, concentration, beta, and volatility use priced positions
            only; cash and balance-only accounts stay outside those
            calculations.
          </p>
          {partial ? (
            <Link
              href="/money?tab=retirement#holdings-coverage"
              className="inline-flex items-center gap-1 text-xs font-semibold text-warning hover:underline"
            >
              Add missing holdings detail <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function SectorExposure({ analytics }: { analytics: PortfolioAnalytics }) {
  const sectors = Object.entries(analytics.sectorExposure).sort(
    (left, right) => right[1] - left[1],
  )
  const usesLookthrough = analytics.concentration.method === 'lookthrough'

  return (
    <SectionCard
      title="Sector exposure"
      description={
        usesLookthrough
          ? 'Underlying sector exposure after fund look-through for the priced positions in this workspace.'
          : 'Sector exposure from the priced fund and security line items in this workspace.'
      }
      variant="surface"
    >
      {sectors.length === 0 ? (
        <p className="text-sm text-text-muted">
          Sector classifications are not available for the current positions.
        </p>
      ) : (
        <div className="space-y-4">
          {sectors.map(([sector, value]) => (
            <div key={sector} className="space-y-1.5">
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="font-medium text-text">{sector}</span>
                <span className="tabular-nums text-text-muted">
                  {formatPercent(value)}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-muted/40">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  )
}

function uniquePerformers(
  analytics: PortfolioAnalytics,
): PositionPerformance[] {
  const bySymbol = new Map<string, PositionPerformance>()
  for (const performer of [
    ...analytics.topPerformers,
    ...analytics.bottomPerformers,
  ]) {
    bySymbol.set(performer.symbol, performer)
  }
  return [...bySymbol.values()].sort(
    (left, right) => right.gainPct - left.gainPct,
  )
}

function PositionReturns({ analytics }: { analytics: PortfolioAnalytics }) {
  const performers = uniquePerformers(analytics)
  return (
    <SectionCard
      title="Return extremes"
      description="Best and worst current unrealized symbol returns—not a complete holdings list, time-weighted performance, or a benchmark comparison."
      variant="surface"
    >
      {performers.length === 0 ? (
        <p className="text-sm text-text-muted">
          Return detail will appear when cost basis and live prices are
          available.
        </p>
      ) : (
        <div className="divide-y divide-border/30">
          {performers.map((performer) => {
            const positive = performer.gainPct >= 0
            return (
              <div
                key={performer.symbol}
                className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 py-3 first:pt-0 last:pb-0"
              >
                <div className="min-w-0">
                  <Link
                    href={`/symbols/${encodeURIComponent(performer.symbol)}`}
                    className="font-semibold text-text hover:text-primary hover:underline"
                  >
                    {performer.symbol}
                  </Link>
                  <p className="mt-1 text-xs text-text-muted">
                    {formatCurrencyWhole(performer.currentValue)} ·{' '}
                    {formatPercent(performer.weightPct)} of analyzed positions
                  </p>
                </div>
                <div className="text-right">
                  <p
                    className={cn(
                      'font-semibold tabular-nums',
                      positive ? 'text-gain' : 'text-loss',
                    )}
                  >
                    {formatPercent(performer.gainPct, { sign: true })}
                  </p>
                  <p className="mt-1 text-xs tabular-nums text-text-muted">
                    {formatCurrencyWhole(performer.gainAmount)}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </SectionCard>
  )
}

function AnalysisContent({ analytics }: { analytics: PortfolioAnalytics }) {
  const concentration = analytics.concentration
  const diversification = analytics.diversificationScore
  const concentrationUsesLookthrough = concentration.method === 'lookthrough'
  const diversificationUsesLookthrough =
    diversification?.method === 'lookthrough'
  const volatility =
    analytics.portfolioVolatility == null
      ? '—'
      : formatPercent(analytics.portfolioVolatility * 100)
  const topHolding =
    concentration.topHoldingName ??
    (concentrationUsesLookthrough
      ? 'Top underlying holding'
      : 'Top line-item holding')

  return (
    <div className="space-y-4">
      <AnalysisScope analytics={analytics} />

      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant={
            analytics.quoteFreshnessStatus === 'fresh' ? 'success' : 'warning'
          }
        >
          {analytics.quoteFreshnessLabel ?? 'Quote freshness unavailable'}
        </Badge>
        <Badge variant="outline">
          {analytics.numPositions} lot{analytics.numPositions === 1 ? '' : 's'}{' '}
          · {analytics.numSymbols} symbol{analytics.numSymbols === 1 ? '' : 's'}
        </Badge>
        {analytics.householdInvestmentAccountsCount != null ? (
          <Badge variant="outline">
            {analytics.householdInvestmentAccountsCount} household investment
            accounts
          </Badge>
        ) : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Priced positions"
          value={formatCurrencyWhole(analytics.portfolioValue.totalValue)}
          detail={`${formatCurrencyWhole(analytics.cashBalanceTotal)} cash is shown separately.`}
        />
        <Metric
          label="Open return"
          value={formatPercent(analytics.portfolioValue.totalGainPct, {
            sign: true,
          })}
          detail={`${formatCurrencyWhole(analytics.portfolioValue.totalGain)} unrealized versus recorded cost basis.`}
        />
        <Metric
          label="Risk posture"
          value={analytics.riskProfile?.level ?? 'Unavailable'}
          detail={`Beta ${analytics.portfolioBeta?.toFixed(2) ?? '—'} · volatility ${volatility}.`}
        />
        <Metric
          label="Diversification"
          value={
            diversification
              ? `${diversification.score.toFixed(0)}/100`
              : 'Unavailable'
          }
          detail={
            diversification
              ? `${diversification.level} · ${diversification.numHoldings} ${
                  diversificationUsesLookthrough
                    ? 'underlying holdings after fund look-through'
                    : 'priced line-item holdings'
                }.`
              : 'Needs classified position detail.'
          }
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <SectionCard
          title="Concentration and risk"
          description="What the represented positions depend on most."
          variant="surface"
        >
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Metric
                label={topHolding}
                value={formatPercent(concentration.topHoldingPct)}
                detail={
                  concentrationUsesLookthrough
                    ? 'Largest underlying company exposure after fund look-through.'
                    : 'Largest priced fund or security line-item exposure.'
                }
              />
              <Metric
                label="Top three"
                value={formatPercent(concentration.top3Pct)}
                detail={
                  concentrationUsesLookthrough
                    ? 'Combined underlying exposure of the three largest holdings after fund look-through.'
                    : 'Combined exposure of the three largest priced fund or security line items.'
                }
              />
              <Metric
                label="Sharpe ratio"
                value={analytics.sharpeRatio?.toFixed(2) ?? '—'}
                detail={
                  analytics.sharpeRatio == null
                    ? 'Not enough portfolio snapshot history for a return series.'
                    : 'Risk-adjusted result from available portfolio snapshot history.'
                }
              />
              <Metric
                label="Look-through coverage"
                value={formatPercent(concentration.lookthroughCoveragePct)}
                detail="Share of represented funds decomposed into underlying exposure."
              />
            </div>
            {analytics.riskProfile ? (
              <div className="rounded-xl border border-border/40 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
                  Risk drivers
                </p>
                <ul className="mt-3 space-y-2 text-sm text-text-muted">
                  {Object.values(analytics.riskProfile.factors).map(
                    (factor) => (
                      <li key={factor} className="flex items-start gap-2">
                        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                        <span>{factor}</span>
                      </li>
                    ),
                  )}
                </ul>
              </div>
            ) : null}
          </div>
        </SectionCard>

        <SectorExposure analytics={analytics} />
      </div>

      <PositionReturns analytics={analytics} />

      <SectionCard variant="surface" padding="sm">
        <div className="flex flex-col gap-3 text-sm text-text-muted sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2">
            <BarChart3 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <p>
              Use allocation goals for household-wide drift and a guarded
              rebalance plan; this panel intentionally does not turn partial
              analytics into a trade recommendation.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/portfolio/drift">
              Review allocation goals <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      </SectionCard>
    </div>
  )
}

export function InvestmentAnalysisPanel() {
  const { data, isLoading, error, refetch, isFetching } =
    usePortfolioAnalytics()

  if (isLoading && !data) {
    return (
      <SectionCard title="Portfolio analysis" variant="surface">
        <div
          aria-busy="true"
          className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
        >
          {['scope', 'return', 'risk', 'diversification'].map((key) => (
            <div
              key={key}
              className="h-28 animate-pulse rounded-xl border border-border/30 bg-surface-muted/20"
            />
          ))}
        </div>
      </SectionCard>
    )
  }

  if (error && !data) {
    return (
      <SectionCard title="Portfolio analysis unavailable" variant="surface">
        <div role="alert" className="space-y-3 text-sm text-text-muted">
          <p>{error.message}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void refetch()}
            disabled={isFetching}
          >
            <RefreshCw
              className={cn('h-4 w-4', isFetching && 'animate-spin')}
            />
            Try again
          </Button>
        </div>
      </SectionCard>
    )
  }

  if (!data || data.numPositions === 0) {
    return (
      <SectionCard title="No position-level analysis yet" variant="surface">
        <div className="space-y-3 text-sm text-text-muted">
          <p>
            Add holdings with symbols and cost basis to calculate concentration,
            sector exposure, and risk.
          </p>
          <Button asChild variant="outline" size="sm">
            <Link href="/money?tab=retirement#holdings-coverage">
              Add holdings detail <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      </SectionCard>
    )
  }

  return <AnalysisContent analytics={data} />
}
