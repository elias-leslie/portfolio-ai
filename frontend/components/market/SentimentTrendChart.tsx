"use client";

import { useState, useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { useFearGreedHistory } from "@/lib/hooks/useMarketIntelligence";
import { TimeframeSelector, Timeframe, timeframeToDays } from "./TimeframeSelector";
import { Loader2 } from "lucide-react";

export function SentimentTrendChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>("1Y");
  const days = timeframeToDays(timeframe);

  const { data, isLoading, error } = useFearGreedHistory(days);

  // Transform data for Recharts
  const chartData = useMemo(() => {
    if (!data?.dates?.length) return [];
    return data.dates.map((date, idx) => ({
      date,
      score: data.scores[idx],
      label: data.labels[idx],
    }));
  }, [data]);

  // Current score (last data point)
  const currentScore = chartData.length > 0 ? chartData[chartData.length - 1].score : null;
  const currentLabel = chartData.length > 0 ? chartData[chartData.length - 1].label : null;

  // Calculate min/max for range display
  const minScore = chartData.length > 0 ? Math.min(...chartData.map((d) => d.score)) : 0;
  const maxScore = chartData.length > 0 ? Math.max(...chartData.map((d) => d.score)) : 100;

  // Format date for X axis
  const formatXAxis = (date: string) => {
    const d = new Date(date);
    return d.toLocaleDateString("en-US", { month: "short" });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (error || !data?.dates?.length) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        Unable to load sentiment data
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Market Sentiment</h3>
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
      </div>

      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
            {/* Background zones */}
            <ReferenceArea y1={0} y2={25} fill="#ef4444" fillOpacity={0.1} />
            <ReferenceArea y1={25} y2={45} fill="#f97316" fillOpacity={0.1} />
            <ReferenceArea y1={45} y2={55} fill="#eab308" fillOpacity={0.1} />
            <ReferenceArea y1={55} y2={75} fill="#84cc16" fillOpacity={0.1} />
            <ReferenceArea y1={75} y2={100} fill="#22c55e" fillOpacity={0.1} />

            <XAxis
              dataKey="date"
              tickFormatter={formatXAxis}
              tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
              axisLine={{ stroke: "var(--color-border)" }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
              axisLine={false}
              tickLine={false}
              width={30}
            />
            <ReferenceLine y={50} stroke="var(--color-border)" strokeDasharray="3 3" />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number) => [`${value}`, "Fear & Greed"]}
              labelFormatter={(label) =>
                new Date(label).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })
              }
            />
            <defs>
              <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="score"
              stroke="#8B5CF6"
              strokeWidth={2}
              fill="url(#sentimentGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Summary row */}
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>
          Fear & Greed:{" "}
          <span className="font-semibold text-text">
            {currentScore} ({currentLabel})
          </span>
        </span>
        <span>
          Range: {minScore.toFixed(0)}–{maxScore.toFixed(0)}
        </span>
      </div>

      {/* Labels on right */}
      <div className="absolute right-2 top-10 text-[10px] text-text-muted hidden sm:block">
        <div className="mb-8">Greed</div>
        <div className="mb-8">Neutral</div>
        <div>Fear</div>
      </div>
    </div>
  );
}
