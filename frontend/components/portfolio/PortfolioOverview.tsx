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
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(6)].map((_, i) => (
          <Card key={i} className="p-6">
            <div className="h-24 animate-pulse rounded-xl bg-surface-muted/60" />
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

      <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-sm text-text-muted">
        {positionCount} live position{positionCount === 1 ? '' : 's'}
        {analytics?.numSymbols != null ? ` · ${analytics.numSymbols} unique symbol${analytics.numSymbols === 1 ? '' : 's'}` : ''}
        {analytics?.cashInclusiveTotalValue != null
          ? ` · ${formatCurrency(analytics.cashInclusiveTotalValue)} including cash`
          : ''}
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="group p-6 transition-shadow duration-200 hover:shadow-lg">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-3 transition-colors duration-200 group-hover:bg-primary/15">
              <DollarSign className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium text-text-muted">
                Total Value
              </div>
              <div className="mt-1 text-2xl font-bold text-text">
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

        <Card className="group p-6 transition-shadow duration-200 hover:shadow-lg">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'rounded-lg p-3 transition-colors duration-200',
                (portfolio?.totalGain ?? 0) >= 0
                  ? 'bg-gain/10 group-hover:bg-gain/15'
                  : 'bg-loss/10 group-hover:bg-loss/15',
              )}
            >
              <TrendingUp className={cn('h-5 w-5', gainColor)} />
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium text-text-muted">
                Total Gain/Loss
              </div>
              <div className={cn('mt-1 text-2xl font-bold', gainColor)}>
                {formatCurrency(portfolio?.totalGain ?? 0)}
              </div>
              <div className={cn('mt-1 text-xs', gainColor)}>
                {formatPercent(portfolio?.totalGainPct ?? 0)}
              </div>
            </div>
          </div>
        </Card>

        <Card className="group p-6 transition-shadow duration-200 hover:shadow-lg">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-accent/10 p-3 transition-colors duration-200 group-hover:bg-accent/15">
              <Activity className="h-5 w-5 text-accent" />
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium text-text-muted">
                Market Sensitivity
              </div>
              <div className="mt-1 text-2xl font-bold text-text">
                {analytics?.portfolioBeta?.toFixed(2) ?? '—'}
              </div>
              <div className="mt-1 text-xs text-text-muted">
                1.0 means it usually moves with the market
              </div>
            </div>
          </div>
        </Card>

        <Card className="group p-6 transition-shadow duration-200 hover:shadow-lg">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-accent/10 p-3 transition-colors duration-200 group-hover:bg-accent/15">
              <Gauge className="h-5 w-5 text-accent" />
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium text-text-muted">
                Typical Swings
              </div>
              <div className="mt-1 text-2xl font-bold text-text">
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
            <h3 className="mb-4 text-sm font-semibold text-text">
              Single-Stock Risk
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-text-muted">Top Holding</span>
                <span className="text-sm font-medium">
                  {analytics.concentration.topHoldingPct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-text-muted">Top 3</span>
                <span className="text-sm font-medium">
                  {analytics.concentration.top3Pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-text-muted">Top 10</span>
                <span className="text-sm font-medium">
                  {analytics.concentration.top10Pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-text-muted">
                  Concentration Score
                </span>
                <span className="text-sm font-medium">
                  {analytics.concentration.herfindahlIndex.toFixed(3)}
                </span>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="mb-4 text-sm font-semibold text-text">
              Where Your Money Is Concentrated
            </h3>
            <div className="space-y-3">
              {Object.entries(analytics.sectorExposure)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 5)
                .map(([sector, percentage]) => (
                  <div
                    key={sector}
                    className="flex justify-between items-center"
                  >
                    <span className="text-sm text-text-muted">
                      {formatDisplayLabel(sector)}
                    </span>
                    <span className="text-sm font-medium">
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
