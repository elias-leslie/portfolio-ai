"use client";

import { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";
import { useIndicatorHistory } from "@/lib/hooks/useMarketIntelligence";
import { TimeframeSelector, Timeframe, timeframeToDays, formatChartDate, calculateTickInterval } from "./TimeframeSelector";
import { Loader2 } from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";

const INDICATOR_CONFIG = {
  sp500: { name: "S&P 500", color: "#3B82F6" },
  vix: { name: "VIX", color: "#EF4444" },
  tnx: { name: "10Y Yield", color: "#F97316" },
  dxy: { name: "Dollar", color: "#10B981" },
};

type IndicatorKey = keyof typeof INDICATOR_CONFIG;

export function IndicatorsTrendChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>("1Y");
  const [highlighted, setHighlighted] = useState<IndicatorKey | null>(null);
  const days = timeframeToDays(timeframe);

  const { data, isLoading, error, dataUpdatedAt } = useIndicatorHistory(days);

  // Transform data for Recharts - merge all indicators by date
  // Include both percentage change (for charting) and actual values (for tooltips)
  const chartData = useMemo(() => {
    if (!data?.sp500?.length) return [];

    return data.sp500.map((point, idx) => ({
      date: point.date,
      sp500: point.pct_change,
      sp500_value: point.close,
      vix: data.vix[idx]?.pct_change ?? 0,
      vix_value: data.vix[idx]?.close ?? 0,
      tnx: data.tnx[idx]?.pct_change ?? 0,
      tnx_value: data.tnx[idx]?.close ?? 0,
      dxy: data.dxy[idx]?.pct_change ?? 0,
      dxy_value: data.dxy[idx]?.close ?? 0,
    }));
  }, [data]);

  // Get current values for summary
  const currentValues = useMemo(() => {
    if (!data?.sp500?.length) return null;
    const last = (arr: { pct_change: number; close: number }[]) =>
      arr.length > 0 ? arr[arr.length - 1] : null;
    return {
      sp500: last(data.sp500),
      vix: last(data.vix),
      tnx: last(data.tnx),
      dxy: last(data.dxy),
    };
  }, [data]);

  // Use shared date formatting and tick calculation
  const formatXAxis = (date: string) => formatChartDate(date, days);
  const tickInterval = useMemo(() => calculateTickInterval(chartData.length), [chartData.length]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (error || !data?.sp500?.length) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        Unable to load indicator data
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Key Indicators</h3>
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
      </div>

      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
            <XAxis
              dataKey="date"
              tickFormatter={formatXAxis}
              tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
              axisLine={{ stroke: "var(--color-border)" }}
              tickLine={false}
              interval={tickInterval}
            />
            <YAxis
              tickFormatter={(v) => `${v}%`}
              tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
              axisLine={false}
              tickLine={false}
              width={40}
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
                const config = INDICATOR_CONFIG[name as IndicatorKey];
                const actualValue = props.payload?.[`${name}_value`];
                // Format actual value based on indicator type
                let formattedValue = "";
                if (name === "sp500") {
                  formattedValue = actualValue?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? "";
                } else if (name === "tnx") {
                  formattedValue = `${actualValue?.toFixed(2) ?? ""}%`;
                } else {
                  formattedValue = actualValue?.toFixed(2) ?? "";
                }
                return [`${formattedValue} (${value >= 0 ? "+" : ""}${value.toFixed(1)}%)`, config?.name || name];
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
            {(Object.keys(INDICATOR_CONFIG) as IndicatorKey[]).map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={INDICATOR_CONFIG[key].color}
                strokeWidth={highlighted === key ? 3 : 1.5}
                dot={false}
                opacity={highlighted === null || highlighted === key ? 1 : 0.2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Interactive legend with current values */}
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {(Object.keys(INDICATOR_CONFIG) as IndicatorKey[]).map((key) => {
            const config = INDICATOR_CONFIG[key];
            const current = currentValues?.[key];
            const pct = current?.pct_change ?? 0;
            return (
              <button
                key={key}
                onClick={() => setHighlighted(highlighted === key ? null : key)}
                className={`flex items-center gap-1 transition-opacity ${
                  highlighted !== null && highlighted !== key ? "opacity-40" : ""
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: config.color }}
                />
                <span className="text-text-muted">
                  {config.name}{" "}
                  <span className={pct >= 0 ? "text-success" : "text-destructive"}>
                    {pct >= 0 ? "+" : ""}
                    {pct.toFixed(1)}%
                  </span>
                </span>
              </button>
            );
          })}
        </div>
        <span className="text-[10px] text-text-muted">
          {dataUpdatedAt ? `Updated ${formatRelativeTime(new Date(dataUpdatedAt).toISOString())}` : ""}
        </span>
      </div>
    </div>
  );
}
