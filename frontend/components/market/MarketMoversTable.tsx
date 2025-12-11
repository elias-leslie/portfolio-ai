"use client";

import { useState } from "react";
import { useMarketMovers } from "@/lib/hooks/useMarketIntelligence";
import { Loader2, TrendingUp, TrendingDown, BarChart3, Zap } from "lucide-react";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { MarketMoverItem } from "@/lib/api/market";

type Tab = "gainers" | "losers" | "volume" | "rvol";

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

function formatRvol(rvol: number | null): string {
  if (rvol === null || rvol === undefined) return "-";
  return `${rvol.toFixed(1)}x`;
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
      <div className="text-xs text-text-muted text-center py-4">
        Unable to load market movers
      </div>
    );
  }

  const getItems = (): MarketMoverItem[] => {
    switch (activeTab) {
      case "gainers":
        return data.gainers;
      case "losers":
        return data.losers;
      case "volume":
        return data.most_active;
      case "rvol":
        return data.top_rvol;
    }
  };

  const items = getItems();

  // Determine which column to highlight based on tab
  const showRvolColumn = activeTab === "rvol";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-text">Market Movers</h3>
        <div className="flex gap-0.5 bg-surface-muted rounded-lg p-0.5">
          <button
            onClick={() => setActiveTab("gainers")}
            className={cn(
              "flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors",
              activeTab === "gainers"
                ? "bg-surface text-gain shadow-sm"
                : "text-text-muted hover:text-text"
            )}
          >
            <TrendingUp className="h-2.5 w-2.5" />
            Gainers
          </button>
          <button
            onClick={() => setActiveTab("losers")}
            className={cn(
              "flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors",
              activeTab === "losers"
                ? "bg-surface text-loss shadow-sm"
                : "text-text-muted hover:text-text"
            )}
          >
            <TrendingDown className="h-2.5 w-2.5" />
            Losers
          </button>
          <button
            onClick={() => setActiveTab("volume")}
            className={cn(
              "flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors",
              activeTab === "volume"
                ? "bg-surface text-text shadow-sm"
                : "text-text-muted hover:text-text"
            )}
          >
            <BarChart3 className="h-2.5 w-2.5" />
            Volume
          </button>
          <button
            onClick={() => setActiveTab("rvol")}
            className={cn(
              "flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors",
              activeTab === "rvol"
                ? "bg-surface text-text shadow-sm"
                : "text-text-muted hover:text-text"
            )}
          >
            <Zap className="h-2.5 w-2.5" />
            RVOL
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="text-text-muted border-b border-border/50">
              <th className="text-left py-1 font-medium">Symbol</th>
              <th className="text-right py-1 font-medium">Price</th>
              <th className="text-right py-1 font-medium">Change</th>
              {showRvolColumn ? (
                <th className="text-right py-1 font-medium">RVOL</th>
              ) : (
                <th className="text-right py-1 font-medium hidden sm:table-cell">Volume</th>
              )}
              <th className="text-right py-1 font-medium hidden md:table-cell">Mkt Cap</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 10).map((item) => (
              <tr
                key={item.symbol}
                className="border-b border-border/30 hover:bg-surface-muted/50 transition-colors"
              >
                <td className="py-1">
                  <div className="flex flex-col">
                    <span className="font-semibold text-text">{item.symbol}</span>
                    {item.name && (
                      <span className="text-text-muted truncate max-w-[100px]" title={item.name}>
                        {item.name.length > 15 ? `${item.name.slice(0, 15)}...` : item.name}
                      </span>
                    )}
                  </div>
                </td>
                <td className="text-right py-1 text-text">
                  ${item.price.toFixed(2)}
                </td>
                <td
                  className={cn(
                    "text-right py-1 font-semibold",
                    item.change_pct >= 0 ? "text-gain" : "text-loss"
                  )}
                >
                  {item.change_pct >= 0 ? "+" : ""}
                  {item.change_pct.toFixed(2)}%
                </td>
                {showRvolColumn ? (
                  <td className="text-right py-1 text-text font-semibold">
                    {formatRvol(item.rvol)}
                  </td>
                ) : (
                  <td className="text-right py-1 text-text-muted hidden sm:table-cell">
                    {formatVolume(item.volume)}
                  </td>
                )}
                <td className="text-right py-1 text-text-muted hidden md:table-cell">
                  {formatMarketCap(item.market_cap)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-[9px] text-text-muted text-right">
        {data.last_updated && `Updated ${formatRelativeTime(data.last_updated)}`}
      </div>
    </div>
  );
}
