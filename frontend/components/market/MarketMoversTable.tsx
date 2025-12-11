"use client";

import { useState } from "react";
import { useMarketMovers } from "@/lib/hooks/useMarketIntelligence";
import { Loader2, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

type Tab = "gainers" | "losers";

function formatVolume(volume: number | null): string {
  if (!volume) return "-";
  if (volume >= 1_000_000) return `${(volume / 1_000_000).toFixed(1)}M`;
  if (volume >= 1_000) return `${(volume / 1_000).toFixed(0)}K`;
  return volume.toString();
}

function formatMarketCap(cap: number | null): string {
  if (!cap) return "-";
  if (cap >= 1_000_000_000_000) return `$${(cap / 1_000_000_000_000).toFixed(1)}T`;
  if (cap >= 1_000_000_000) return `$${(cap / 1_000_000_000).toFixed(1)}B`;
  if (cap >= 1_000_000) return `$${(cap / 1_000_000).toFixed(0)}M`;
  return `$${cap.toLocaleString()}`;
}

export function MarketMoversTable() {
  const [activeTab, setActiveTab] = useState<Tab>("gainers");
  const { data, isLoading, error } = useMarketMovers(10);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="h-5 w-5 animate-spin text-text-muted" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-sm text-text-muted text-center py-4">
        Unable to load market movers
      </div>
    );
  }

  const items = activeTab === "gainers" ? data.gainers : data.losers;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Market Movers</h3>
        <div className="flex gap-1 bg-surface-muted rounded-lg p-0.5">
          <button
            onClick={() => setActiveTab("gainers")}
            className={cn(
              "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
              activeTab === "gainers"
                ? "bg-surface text-gain shadow-sm"
                : "text-text-muted hover:text-text"
            )}
          >
            <TrendingUp className="h-3 w-3" />
            Gainers
          </button>
          <button
            onClick={() => setActiveTab("losers")}
            className={cn(
              "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
              activeTab === "losers"
                ? "bg-surface text-loss shadow-sm"
                : "text-text-muted hover:text-text"
            )}
          >
            <TrendingDown className="h-3 w-3" />
            Losers
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-muted border-b border-border/50">
              <th className="text-left py-1.5 font-medium">Symbol</th>
              <th className="text-right py-1.5 font-medium">Price</th>
              <th className="text-right py-1.5 font-medium">Change</th>
              <th className="text-right py-1.5 font-medium hidden sm:table-cell">Volume</th>
              <th className="text-right py-1.5 font-medium hidden md:table-cell">Mkt Cap</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 5).map((item) => (
              <tr
                key={item.symbol}
                className="border-b border-border/30 hover:bg-surface-muted/50 transition-colors"
              >
                <td className="py-1.5">
                  <div className="flex flex-col">
                    <span className="font-semibold text-text">{item.symbol}</span>
                    {item.name && (
                      <span className="text-text-muted truncate max-w-[120px]" title={item.name}>
                        {item.name.length > 18 ? `${item.name.slice(0, 18)}...` : item.name}
                      </span>
                    )}
                  </div>
                </td>
                <td className="text-right py-1.5 text-text">
                  ${item.price.toFixed(2)}
                </td>
                <td
                  className={cn(
                    "text-right py-1.5 font-semibold",
                    item.change_pct >= 0 ? "text-gain" : "text-loss"
                  )}
                >
                  {item.change_pct >= 0 ? "+" : ""}
                  {item.change_pct.toFixed(2)}%
                </td>
                <td className="text-right py-1.5 text-text-muted hidden sm:table-cell">
                  {formatVolume(item.volume)}
                </td>
                <td className="text-right py-1.5 text-text-muted hidden md:table-cell">
                  {formatMarketCap(item.market_cap)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-[10px] text-text-muted text-right">
        Source: {data.source === "yahooquery" ? "Yahoo Finance" : "Alpaca"} • Updates every 15 min
      </div>
    </div>
  );
}
