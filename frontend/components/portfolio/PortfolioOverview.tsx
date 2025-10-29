"use client";

import { usePortfolio, usePortfolioAnalytics } from "@/lib/hooks/usePortfolio";
import { Card } from "@/components/ui/card";

export function PortfolioOverview() {
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio();
  const { data: analytics, isLoading: analyticsLoading } =
    usePortfolioAnalytics();

  if (portfolioLoading || analyticsLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="p-6">
            <div className="h-24 animate-pulse rounded bg-surface-muted/60" />
          </Card>
        ))}
      </div>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  };

  const gainColor = (portfolio?.total_gain ?? 0) >= 0 ? "text-gain" : "text-loss";

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="p-6">
          <div className="text-sm font-medium text-text-muted">
            Total Value
          </div>
          <div className="mt-2 text-2xl font-bold">
            {formatCurrency(portfolio?.total_value ?? 0)}
          </div>
          <div className="mt-1 text-xs text-text-muted">
            Cost: {formatCurrency(portfolio?.total_cost_basis ?? 0)}
          </div>
        </Card>

        <Card className="p-6">
          <div className="text-sm font-medium text-text-muted">
            Total Gain/Loss
          </div>
          <div className={`mt-2 text-2xl font-bold ${gainColor}`}>
            {formatCurrency(portfolio?.total_gain ?? 0)}
          </div>
          <div className={`mt-1 text-xs ${gainColor}`}>
            {formatPercent(portfolio?.total_gain_pct ?? 0)}
          </div>
        </Card>

        <Card className="p-6">
          <div className="text-sm font-medium text-text-muted">
            Portfolio Beta
          </div>
          <div className="mt-2 text-2xl font-bold">
            {analytics?.portfolio_beta?.toFixed(2) ?? "—"}
          </div>
          <div className="mt-1 text-xs text-text-muted">
            vs. Market (1.0)
          </div>
        </Card>

        <Card className="p-6">
          <div className="text-sm font-medium text-text-muted">
            Volatility
          </div>
          <div className="mt-2 text-2xl font-bold">
            {analytics?.portfolio_volatility
              ? `${(analytics.portfolio_volatility * 100).toFixed(1)}%`
              : "—"}
          </div>
          <div className="mt-1 text-xs text-text-muted">
            Annualized
          </div>
        </Card>
      </div>

      {/* Concentration & Sector Exposure */}
      {analytics && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="p-6">
            <h3 className="mb-4 text-sm font-semibold text-text">Concentration Risk</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-text-muted">
                  Top Holding
                </span>
                <span className="text-sm font-medium">
                  {analytics.concentration.top_holding_pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-text-muted">Top 3</span>
                <span className="text-sm font-medium">
                  {analytics.concentration.top_3_pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-text-muted">Top 10</span>
                <span className="text-sm font-medium">
                  {analytics.concentration.top_10_pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-text-muted">
                  Herfindahl Index
                </span>
                <span className="text-sm font-medium">
                  {analytics.concentration.herfindahl_index.toFixed(3)}
                </span>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="mb-4 text-sm font-semibold text-text">Sector Exposure</h3>
            <div className="space-y-3">
              {Object.entries(analytics.sector_exposure)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 5)
                .map(([sector, percentage]) => (
                  <div
                    key={sector}
                    className="flex justify-between items-center"
                  >
                    <span className="text-sm text-text-muted">
                      {sector}
                    </span>
                    <span className="text-sm font-medium">
                      {percentage.toFixed(1)}%
                    </span>
                  </div>
                ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
