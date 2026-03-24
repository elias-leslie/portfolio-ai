'use client'

import { Activity, DollarSign, Gauge, TrendingUp } from 'lucide-react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { Card } from '@/components/ui/card'
import { usePortfolio, usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { cn } from '@/lib/utils'
import { AssetAllocation } from './AssetAllocation'
import { JennyOperatorPanel } from './JennyOperatorPanel'
import { PortfolioCoachAlerts } from './PortfolioCoachAlerts'
import { DiversificationScore } from './DiversificationScore'
import { PortfolioStats } from './PortfolioStats'
import { RiskProfile } from './RiskProfile'
import { TopPerformers } from './TopPerformers'
import { formatCurrency, formatDisplayLabel, formatPercent } from './portfolio-utils'

export function PortfolioOverview() {
  const {
    data: portfolio,
    isLoading: portfolioLoading,
    error: portfolioError,
    refetch: refetchPortfolio,
    isFetching: portfolioFetching,
  } = usePortfolio()
  const {
    data: analytics,
    isLoading: analyticsLoading,
    error: analyticsError,
    refetch: refetchAnalytics,
    isFetching: analyticsFetching,
  } = usePortfolioAnalytics()

  const isInitialLoading =
    (!portfolio && portfolioLoading) || (!analytics && analyticsLoading)

  if (isInitialLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[...Array(6)].map((_, i) => (
          <Card key={i} className="p-6">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 animate-pulse rounded-lg bg-surface-muted/60" />
              <div className="flex-1 space-y-2">
                <div className="h-3 w-20 animate-pulse rounded bg-surface-muted/40" />
                <div className="h-6 w-28 animate-pulse rounded bg-surface-muted/60" />
                <div className="h-3 w-32 animate-pulse rounded bg-surface-muted/30" />
              </div>
            </div>
          </Card>
        ))}
      </div>
    )
  }

  if (!portfolio && !analytics && (portfolioError || analyticsError)) {
    return (
      <LoadErrorState
        title="Failed to load portfolio overview."
        detail={
          portfolioError?.message ??
          analyticsError?.message ??
          'Retry to refresh portfolio value, concentration, and Jenny guidance.'
        }
        onRetry={() => {
          void refetchPortfolio()
          void refetchAnalytics()
        }}
        isRetrying={portfolioFetching || analyticsFetching}
      />
    )
  }

  const gainColor = (portfolio?.totalGain ?? 0) >= 0 ? 'text-gain' : 'text-loss'
  const hasPartialError = Boolean(portfolioError || analyticsError)
  const positionCount = portfolio?.positions.length ?? 0

  return (
    <div className="space-y-6">
      {hasPartialError ? (
        <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Some portfolio signals are unavailable right now. Core balances are still shown below.
        </div>
      ) : null}

      <div className="rounded-xl border border-border/30 border-l-primary/50 border-l-2 bg-gradient-to-r from-primary/[0.04] to-surface/40 px-4 py-3 text-sm text-text-muted">
        {positionCount} live position{positionCount === 1 ? '' : 's'}
        {analytics?.numSymbols != null ? ` · ${analytics.numSymbols} unique symbol${analytics.numSymbols === 1 ? '' : 's'}` : ''}
        {analytics?.cashInclusiveTotalValue != null
          ? ` · ${formatCurrency(analytics.cashInclusiveTotalValue)} including cash`
          : ''}
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 animate-stagger">
        <Card className="group p-6 transition-all duration-200 hover:shadow-md hover:border-primary/30">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2.5 transition-all duration-200 group-hover:bg-primary/15 group-hover:shadow-[0_0_12px_-3px] group-hover:shadow-primary/20">
              <DollarSign className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1">
              <div className="text-xs font-semibold uppercase tracking-widest text-text-muted">
                Total Value
              </div>
              <div className="mt-1 font-display italic text-2xl tabular-nums text-text">
                {formatCurrency(portfolio?.totalValue ?? 0)}
              </div>
              <div className="mt-1 text-xs text-text-muted">
                Cost: {formatCurrency(portfolio?.totalCostBasis ?? 0)}
              </div>
              <div className="mt-1 text-xs text-text-muted">
                Cash reserve: {formatCurrency(portfolio?.cashBalanceTotal ?? 0)}
              </div>
            </div>
          </div>
        </Card>

        <Card className={cn('group p-6 transition-all duration-200 hover:shadow-md', (portfolio?.totalGain ?? 0) >= 0 ? 'hover:border-gain/30' : 'hover:border-loss/30')}>
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'rounded-lg p-2.5 transition-all duration-200',
                (portfolio?.totalGain ?? 0) >= 0
                  ? 'bg-gain/10 group-hover:bg-gain/15 group-hover:shadow-[0_0_12px_-3px] group-hover:shadow-gain/20'
                  : 'bg-loss/10 group-hover:bg-loss/15 group-hover:shadow-[0_0_12px_-3px] group-hover:shadow-loss/20',
              )}
            >
              <TrendingUp className={cn('h-5 w-5', gainColor)} />
            </div>
            <div className="flex-1">
              <div className="text-xs font-semibold uppercase tracking-widest text-text-muted">
                Total Gain/Loss
              </div>
              <div className={cn('mt-1 font-display italic text-2xl tabular-nums', gainColor)}>
                {formatCurrency(portfolio?.totalGain ?? 0)}
              </div>
              <div className={cn('mt-1 text-xs', gainColor)}>
                {formatPercent(portfolio?.totalGainPct ?? 0)}
              </div>
            </div>
          </div>
        </Card>

        <Card className="group p-6 transition-all duration-200 hover:shadow-md hover:border-accent/30">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-accent/10 p-2.5 transition-all duration-200 group-hover:bg-accent/15 group-hover:shadow-[0_0_12px_-3px] group-hover:shadow-accent/20">
              <Activity className="h-5 w-5 text-accent" />
            </div>
            <div className="flex-1">
              <div className="text-xs font-semibold uppercase tracking-widest text-text-muted">
                Market Sensitivity
              </div>
              <div className="mt-1 font-display italic text-2xl tabular-nums text-text">
                {analytics?.portfolioBeta?.toFixed(2) ?? '—'}
              </div>
              <div className="mt-1 text-xs text-text-muted">
                1.0 means it usually moves with the market
              </div>
            </div>
          </div>
        </Card>

        <Card className="group p-6 transition-all duration-200 hover:shadow-md hover:border-accent/30">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-accent/10 p-2.5 transition-all duration-200 group-hover:bg-accent/15 group-hover:shadow-[0_0_12px_-3px] group-hover:shadow-accent/20">
              <Gauge className="h-5 w-5 text-accent" />
            </div>
            <div className="flex-1">
              <div className="text-xs font-semibold uppercase tracking-widest text-text-muted">
                Typical Swings
              </div>
              <div className="mt-1 font-display italic text-2xl tabular-nums text-text">
                {analytics?.portfolioVolatility
                  ? `${(analytics.portfolioVolatility * 100).toFixed(1)}%`
                  : '—'}
              </div>
              <div className="mt-1 text-xs text-text-muted">Based on recent history</div>
            </div>
          </div>
        </Card>

        {analytics?.diversificationScore ? (
          <DiversificationScore diversification={analytics.diversificationScore} />
        ) : (
          <Card className="p-6">
            <div className="text-sm font-medium text-text-muted">Diversification</div>
            <div className="mt-2 text-sm text-text-muted">
              Diversification scoring is unavailable until analytics refresh successfully.
            </div>
          </Card>
        )}

        {analytics ? (
          <PortfolioStats analytics={analytics} />
        ) : (
          <Card className="p-6">
            <div className="text-sm font-medium text-text-muted">Portfolio Stats</div>
            <div className="mt-2 text-sm text-text-muted">
              Sharpe, symbol breadth, and risk statistics will return once analytics are back.
            </div>
          </Card>
        )}
      </div>

      {portfolio && analytics && (
        <PortfolioCoachAlerts portfolio={portfolio} analytics={analytics} />
      )}

      <JennyOperatorPanel />

      {/* Risk Profile (if available) */}
      {analytics?.riskProfile ? (
        <RiskProfile riskProfile={analytics.riskProfile} />
      ) : analytics ? (
        <Card className="p-6 text-sm text-text-muted">
          Risk profile is not available yet for the current holdings mix.
        </Card>
      ) : null}

      {portfolio && portfolio.positions.length === 0 ? (
        <Card className="p-6 text-sm text-text-muted">
          No live positions yet. Add a holding below to unlock concentration, risk, and performance coaching.
        </Card>
      ) : null}

      {/* Top Performers and Asset Allocation */}
      {analytics ? (
        <div className="grid gap-4 md:grid-cols-2">
          <TopPerformers
            topPerformers={analytics.topPerformers}
            bottomPerformers={analytics.bottomPerformers}
          />
          <AssetAllocation topPerformers={analytics.topPerformers} />
        </div>
      ) : (
        <Card className="p-6 text-sm text-text-muted">
          Top-performer and allocation breakdowns are waiting on portfolio analytics to refresh.
        </Card>
      )}

      {/* Concentration & Sector Exposure */}
      {analytics ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="p-6">
            <h3 className="mb-4 font-display text-lg tracking-tight text-text">
              Single-Stock Risk
            </h3>
            <div className="space-y-2.5">
              {[
                { label: 'Top Holding', value: `${analytics.concentration.topHoldingPct.toFixed(1)}%` },
                { label: 'Top 3', value: `${analytics.concentration.top3Pct.toFixed(1)}%` },
                { label: 'Top 10', value: `${analytics.concentration.top10Pct.toFixed(1)}%` },
                { label: 'Concentration Score', value: analytics.concentration.herfindahlIndex.toFixed(3) },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-sm text-text-muted">{label}</span>
                  <span className="text-sm font-medium tabular-nums">{value}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="mb-4 font-display text-lg tracking-tight text-text">
              Where Your Money Is Concentrated
            </h3>
            <div className="space-y-2.5">
              {Object.entries(analytics.sectorExposure)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 5)
                .map(([sector, percentage]) => (
                  <div
                    key={sector}
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm text-text-muted">
                      {formatDisplayLabel(sector)}
                    </span>
                    <span className="text-sm font-medium tabular-nums">
                      {percentage.toFixed(1)}%
                    </span>
                  </div>
                ))}
            </div>
          </Card>
        </div>
      ) : (
        <Card className="p-6 text-sm text-text-muted">
          Concentration and sector exposure require portfolio analytics and will return once that query succeeds.
        </Card>
      )}
    </div>
  )
}
