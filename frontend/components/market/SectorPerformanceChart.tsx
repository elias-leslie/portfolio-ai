"use client";

import { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import { useSectorHistory } from "@/lib/hooks/useMarketIntelligence";
import { TimeframeSelector, Timeframe, timeframeToDays } from "./TimeframeSelector";
import { Loader2 } from "lucide-react";

// Distinct colors for each sector
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

export function SectorPerformanceChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>("1Y");
  const [highlightedSector, setHighlightedSector] = useState<string | null>(null);
  const days = timeframeToDays(timeframe);

  const { data, isLoading, error } = useSectorHistory(days);

  // Transform data for Recharts
  // Include both percentage change (for charting) and actual close price (for tooltips)
  const chartData = useMemo(() => {
    if (!data?.sectors?.length) return [];

    // Get all unique dates from the first sector (they should all have same dates)
    const firstSector = data.sectors[0];
    if (!firstSector?.data?.length) return [];

    return firstSector.data.map((point, idx) => {
      const entry: Record<string, number | string> = { date: point.date };
      data.sectors.forEach((sector) => {
        if (sector.data[idx]) {
          entry[sector.symbol] = sector.data[idx].pct_change;
          entry[`${sector.symbol}_price`] = sector.data[idx].close;
        }
      });
      return entry;
    });
  }, [data]);

  // Format date for X axis
  const formatXAxis = (date: string) => {
    // Append T12:00:00 to avoid timezone shift
    const d = new Date(date + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "short" });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (error || !data?.sectors?.length) {
    return (
      <div className="flex items-center justify-center h-64 text-text-muted text-sm">
        Unable to load sector data
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Sector Performance</h3>
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
            <XAxis
              dataKey="date"
              tickFormatter={formatXAxis}
              tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
              axisLine={{ stroke: "var(--color-border)" }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(v) => `${v}%`}
              tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
              axisLine={false}
              tickLine={false}
              width={45}
            />
            <ReferenceLine y={0} stroke="var(--color-border)" strokeDasharray="3 3" />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number, name: string, props: { payload?: Record<string, number> }) => {
                const sector = data.sectors.find((s) => s.symbol === name);
                const price = props.payload?.[`${name}_price`];
                const formattedPrice = price?.toFixed(2) ?? "";
                return [`$${formattedPrice} (${value >= 0 ? "+" : ""}${value.toFixed(1)}%)`, sector?.name || name];
              }}
              labelFormatter={(label) =>
                // Append T12:00:00 to avoid timezone shift
                new Date(label + "T12:00:00").toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })
              }
            />
            {data.sectors.map((sector) => (
              <Line
                key={sector.symbol}
                type="monotone"
                dataKey={sector.symbol}
                stroke={SECTOR_COLORS[sector.symbol] || "#888"}
                strokeWidth={highlightedSector === sector.symbol ? 3 : 1.5}
                dot={false}
                opacity={
                  highlightedSector === null || highlightedSector === sector.symbol
                    ? 1
                    : 0.2
                }
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Interactive Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {data.sectors.map((sector) => (
          <button
            key={sector.symbol}
            onClick={() =>
              setHighlightedSector(
                highlightedSector === sector.symbol ? null : sector.symbol
              )
            }
            className={`transition-opacity ${
              highlightedSector !== null && highlightedSector !== sector.symbol
                ? "opacity-40"
                : ""
            }`}
          >
            <span
              className="font-medium"
              style={{ color: SECTOR_COLORS[sector.symbol] || "#888" }}
            >
              {sector.name}
            </span>
            <span>
              {" "}
              <span
                className={
                  sector.current_pct >= 0 ? "text-gain" : "text-loss"
                }
              >
                {sector.current_pct >= 0 ? "+" : ""}
                {sector.current_pct.toFixed(1)}%
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
