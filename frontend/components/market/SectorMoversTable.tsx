"use client";

import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn, checkDataFreshness, formatDate } from "@/lib/utils";
import { useMarketStatus } from "@/lib/hooks/useMarketIntelligence";

// Sector colors matching SectorPerformanceChart
const SECTOR_COLORS: Record<string, string> = {
  XLK: "#8B5CF6", // Purple - Technology
  XLF: "#3B82F6", // Blue - Financials
  XLE: "#F97316", // Orange - Energy
  XLV: "#10B981", // Green - Healthcare
  XLY: "#EC4899", // Pink - Consumer Discretionary
  XLP: "#6366F1", // Indigo - Consumer Staples
  XLI: "#EAB308", // Yellow - Industrials
  XLU: "#14B8A6", // Teal - Utilities
  XLRE: "#F43F5E", // Rose - Real Estate
  XLB: "#84CC16", // Lime - Materials
  XLC: "#06B6D4", // Cyan - Communication Services
};

interface SectorInfo {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
}

interface SectorMoversTableProps {
  leading: SectorInfo[];
  neutral: SectorInfo[];
  lagging: SectorInfo[];
  lastUpdated?: string;
}

type SectorWithStatus = SectorInfo & { status: "leading" | "neutral" | "lagging" };

export function SectorMoversTable({ leading, neutral, lagging, lastUpdated }: SectorMoversTableProps) {
  const { data: marketStatus } = useMarketStatus();

  // Combine and sort all sectors by change_pct descending
  const allSectors: SectorWithStatus[] = [
    ...leading.map((s) => ({ ...s, status: "leading" as const })),
    ...neutral.map((s) => ({ ...s, status: "neutral" as const })),
    ...lagging.map((s) => ({ ...s, status: "lagging" as const })),
  ].sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0));

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "leading":
        return <TrendingUp className="h-4 w-4 text-gain" />;
      case "lagging":
        return <TrendingDown className="h-4 w-4 text-loss" />;
      default:
        return <Minus className="h-4 w-4 text-text-muted" />;
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Sector Movers</h3>
        <div className="flex gap-2 text-xs text-text-muted">
          <span className="flex items-center gap-1">
            <TrendingUp className="h-3 w-3 text-gain" />
            {leading.length}
          </span>
          <span className="flex items-center gap-1">
            <Minus className="h-3 w-3" />
            {neutral.length}
          </span>
          <span className="flex items-center gap-1">
            <TrendingDown className="h-3 w-3 text-loss" />
            {lagging.length}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-text-muted border-b border-border/50">
              <th className="text-left py-2 font-medium">Sector</th>
              <th className="text-right py-2 font-medium">Change</th>
              <th className="text-center py-2 font-medium w-10">Status</th>
            </tr>
          </thead>
          <tbody>
            {allSectors.map((sector) => (
              <tr
                key={sector.symbol}
                className="border-b border-border/30 hover:bg-surface-muted/50 transition-colors"
              >
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: SECTOR_COLORS[sector.symbol] || "#888" }}
                    />
                    <span className="font-medium text-text">{sector.name}</span>
                  </div>
                </td>
                <td
                  className={cn(
                    "text-right py-2 font-semibold",
                    (sector.change_pct ?? 0) >= 0 ? "text-gain" : "text-loss"
                  )}
                >
                  {(sector.change_pct ?? 0) >= 0 ? "+" : ""}
                  {(sector.change_pct ?? 0).toFixed(2)}%
                </td>
                <td className="text-center py-2">
                  {getStatusIcon(sector.status)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {lastUpdated && (() => {
        const dataDate = lastUpdated.split("T")[0];
        const freshness = checkDataFreshness(dataDate, marketStatus?.expected_data_date);
        return (
          <div className="text-[10px] text-text-muted text-right" title={freshness.tooltip}>
            Data as of {formatDate(dataDate, false)} {freshness.indicator}
          </div>
        );
      })()}
    </div>
  );
}
