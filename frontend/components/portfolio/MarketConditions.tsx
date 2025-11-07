"use client";

import { useState } from "react";
import { useMarketConditions } from "@/lib/hooks/useMarket";
import { Card } from "@/components/ui/card";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";

export function MarketConditions() {
  const { data: market, isLoading } = useMarketConditions();
  const [showDetails, setShowDetails] = useState(false);

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="h-48 animate-pulse rounded bg-surface-muted/60" />
      </Card>
    );
  }

  const indicators = [
    {
      name: "S&P 500",
      value: market?.sp500.price,
      change: market?.sp500.change_pct,
      timestamp: market?.sp500.last_updated,
    },
    {
      name: "VIX",
      value: market?.vix.price,
      change: null,
      timestamp: market?.vix.last_updated,
    },
    {
      name: "10Y Treasury",
      value: market?.tnx.yield,
      suffix: "%",
      change: null,
      timestamp: market?.tnx.last_updated,
    },
    {
      name: "US Dollar",
      value: market?.dxy.price,
      change: null,
      timestamp: market?.dxy.last_updated,
    },
  ];

  const health = market?.health;
  const overallScore = health?.overall_score ?? 50;

  // Color based on score
  const getScoreColor = (score: number) => {
    if (score >= 70) return "text-green-500";
    if (score >= 55) return "text-green-400";
    if (score >= 45) return "text-yellow-500";
    if (score >= 30) return "text-orange-500";
    return "text-red-500";
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 70) return "bg-green-500/20";
    if (score >= 55) return "bg-green-400/20";
    if (score >= 45) return "bg-yellow-500/20";
    if (score >= 30) return "bg-orange-500/20";
    return "bg-red-500/20";
  };

  const getSignalColor = (signal: string) => {
    if (signal === "Bullish") return "text-green-500";
    if (signal === "Bearish") return "text-red-500";
    return "text-yellow-500";
  };

  return (
    <Card className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text">Market Conditions</h2>
        {health && (
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className={`text-2xl font-bold ${getScoreColor(overallScore)}`}>
                {overallScore}
              </div>
              <div className="text-xs text-text-muted">{health.overall_label}</div>
            </div>
            <div
              className={`h-12 w-12 rounded-full ${getScoreBgColor(overallScore)} flex items-center justify-center`}
            >
              <div className={`text-lg font-bold ${getScoreColor(overallScore)}`}>
                {overallScore >= 70 ? "🚀" : overallScore >= 55 ? "📈" : overallScore >= 45 ? "😐" : overallScore >= 30 ? "📉" : "⚠️"}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main Indicators */}
      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        {indicators.map((indicator) => (
          <div key={indicator.name} className="space-y-1">
            <div className="text-xs text-text-muted">{indicator.name}</div>
            <div className="text-lg font-semibold text-text">
              {indicator.value !== null && indicator.value !== undefined
                ? `${indicator.value.toFixed(2)}${indicator.suffix || ""}`
                : "—"}
            </div>
            {indicator.change !== null && indicator.change !== undefined && (
              <div
                className={`text-xs font-medium ${
                  indicator.change >= 0 ? "text-gain" : "text-loss"
                }`}
              >
                {indicator.change >= 0 ? "+" : ""}
                {indicator.change.toFixed(2)}%
              </div>
            )}
            {indicator.timestamp && (
              <div className="text-xs text-text-muted/70">
                {formatRelativeTime(indicator.timestamp)}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Expandable Details */}
      {health && health.components && health.components.length > 0 && (
        <div className="border-t border-border pt-4">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex w-full items-center justify-between text-sm text-text-muted hover:text-text transition-colors"
          >
            <span className="font-medium">
              {showDetails ? "Hide Details" : "Show Component Breakdown"}
            </span>
            {showDetails ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>

          {showDetails && (
            <div className="mt-4 space-y-3">
              {health.components.map((component, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-border bg-surface-elev/50 p-3"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <div className="flex flex-col">
                      <div className="font-medium text-text text-sm">
                        {component.name}
                      </div>
                      {component.last_updated && (
                        <div className="text-xs text-text-muted/60">
                          {formatRelativeTime(component.last_updated)}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className={`text-xs font-semibold ${getSignalColor(component.signal)}`}>
                        {component.signal}
                      </div>
                      <div className={`text-sm font-bold ${getScoreColor(component.score)}`}>
                        {component.score}/100
                      </div>
                    </div>
                  </div>
                  <div className="mb-2 text-xs text-text-muted">
                    Value: {component.value !== null ? component.value.toFixed(2) : "N/A"}
                  </div>
                  <div className="text-xs text-text-muted italic">
                    {component.interpretation}
                  </div>
                  <div className="mt-2 h-1.5 w-full rounded-full bg-surface-muted/60">
                    <div
                      className={`h-full rounded-full transition-all ${
                        component.score >= 70
                          ? "bg-green-500"
                          : component.score >= 55
                          ? "bg-green-400"
                          : component.score >= 45
                          ? "bg-yellow-500"
                          : component.score >= 30
                          ? "bg-orange-500"
                          : "bg-red-500"
                      }`}
                      style={{ width: `${component.score}%` }}
                    />
                  </div>
                </div>
              ))}

              {/* Sector Performance */}
              {health.sectors && health.sectors.length > 0 && (
                <div className="mt-4 rounded-lg border border-border bg-surface-elev/50 p-3">
                  <h3 className="mb-3 text-sm font-medium text-text">
                    Sector Performance (Today)
                  </h3>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {health.sectors.map((sector, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between rounded bg-surface-muted/30 px-2 py-1.5"
                      >
                        <div className="flex flex-col">
                          <span className="text-xs font-medium text-text">
                            {sector.name}
                          </span>
                          <span className="text-xs text-text-muted">
                            {sector.symbol}
                          </span>
                          {sector.last_updated && (
                            <span className="text-xs text-text-muted/60">
                              {formatRelativeTime(sector.last_updated)}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {sector.change_pct !== null && sector.change_pct !== undefined ? (
                            <span
                              className={`text-xs font-semibold ${
                                sector.change_pct > 0
                                  ? "text-green-500"
                                  : sector.change_pct < 0
                                  ? "text-red-500"
                                  : "text-yellow-500"
                              }`}
                            >
                              {sector.change_pct > 0 ? "+" : ""}
                              {sector.change_pct.toFixed(2)}%
                            </span>
                          ) : (
                            <span className="text-xs text-text-muted">N/A</span>
                          )}
                          <span
                            className={`text-xs font-medium ${
                              sector.signal === "Leading"
                                ? "text-green-500"
                                : sector.signal === "Lagging"
                                ? "text-red-500"
                                : "text-yellow-500"
                            }`}
                          >
                            {sector.signal === "Leading" ? "🟢" : sector.signal === "Lagging" ? "🔴" : "🟡"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-3 rounded-lg bg-surface-muted/30 p-3 text-xs text-text-muted">
                <p className="mb-1 font-medium text-text">How scores are calculated:</p>
                <ul className="list-inside list-disc space-y-1">
                  <li>VIX: Lower volatility = more bullish (inverted scale)</li>
                  <li>S&P 500: Higher levels = stronger market sentiment</li>
                  <li>Treasury Yields: Moderate yields preferred (Goldilocks)</li>
                  <li>US Dollar: Stable/weak dollar supports stock prices</li>
                  <li>Sectors: Ranked by daily performance (Leading/Neutral/Lagging)</li>
                </ul>
                <p className="mt-2 text-xs">
                  Overall score is the average of all components. Updates in real-time as market data refreshes.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
