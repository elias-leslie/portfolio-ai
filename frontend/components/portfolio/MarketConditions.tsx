"use client";

import { useMarketConditions } from "@/lib/hooks/useMarket";
import { Card } from "@/components/ui/card";

export function MarketConditions() {
  const { data: market, isLoading } = useMarketConditions();

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="h-32 animate-pulse bg-muted rounded" />
      </Card>
    );
  }

  const indicators = [
    {
      name: "S&P 500",
      value: market?.sp500.price,
      change: market?.sp500.change_pct,
    },
    {
      name: "VIX",
      value: market?.vix.price,
      change: null,
    },
    {
      name: "10Y Treasury",
      value: market?.tnx.yield,
      suffix: "%",
      change: null,
    },
    {
      name: "US Dollar",
      value: market?.dxy.price,
      change: null,
    },
  ];

  return (
    <Card className="p-6">
      <h2 className="text-lg font-semibold mb-4">Market Conditions</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {indicators.map((indicator) => (
          <div key={indicator.name} className="space-y-1">
            <div className="text-xs text-muted-foreground">
              {indicator.name}
            </div>
            <div className="text-lg font-semibold">
              {indicator.value !== null && indicator.value !== undefined
                ? `${indicator.value.toFixed(2)}${indicator.suffix || ""}`
                : "—"}
            </div>
            {indicator.change !== null && (
              <div
                className={`text-xs ${
                  indicator.change >= 0 ? "text-green-600" : "text-red-600"
                }`}
              >
                {indicator.change >= 0 ? "+" : ""}
                {indicator.change.toFixed(2)}%
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
