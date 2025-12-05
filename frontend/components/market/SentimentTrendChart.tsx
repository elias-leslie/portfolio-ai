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
  Line,
  ComposedChart,
} from "recharts";
import { useFearGreedHistory, useNewsSentimentHistory } from "@/lib/hooks/useMarketIntelligence";
import { TimeframeSelector, Timeframe, timeframeToDays } from "./TimeframeSelector";
import { Loader2 } from "lucide-react";

// Convert news sentiment (-1 to +1) to 0-100 scale for chart alignment
function normalizeNewsSentiment(score: number): number {
  return ((score + 1) / 2) * 100;
}

export function SentimentTrendChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>("1Y");
  const days = timeframeToDays(timeframe);

  const { data: fearGreedData, isLoading: fgLoading, error: fgError } = useFearGreedHistory(days);
  const { data: newsData, isLoading: newsLoading } = useNewsSentimentHistory(days, "daily");

  // Merge Fear & Greed and News Sentiment data by date
  const chartData = useMemo(() => {
    if (!fearGreedData?.dates?.length) return [];

    // Create a map of news sentiment by date
    const newsMap = new Map<string, number>();
    if (newsData?.dates?.length) {
      newsData.dates.forEach((date, idx) => {
        // Normalize date to YYYY-MM-DD for matching
        const dateKey = date.split("T")[0];
        newsMap.set(dateKey, newsData.scores[idx]);
      });
    }

    return fearGreedData.dates.map((date, idx) => {
      const dateKey = date.split("T")[0];
      const newsScore = newsMap.get(dateKey);
      return {
        date,
        score: fearGreedData.scores[idx],
        label: fearGreedData.labels[idx],
        newsSentiment: newsScore !== undefined ? normalizeNewsSentiment(newsScore) : null,
        newsRaw: newsScore, // Keep raw score for tooltip
      };
    });
  }, [fearGreedData, newsData]);

  const isLoading = fgLoading || newsLoading;

  // Current score (last data point)
  const currentScore = chartData.length > 0 ? chartData[chartData.length - 1].score : null;
  const currentLabel = chartData.length > 0 ? chartData[chartData.length - 1].label : null;

  // Calculate min/max for range display
  const minScore = chartData.length > 0 ? Math.min(...chartData.map((d) => d.score)) : 0;
  const maxScore = chartData.length > 0 ? Math.max(...chartData.map((d) => d.score)) : 100;

  // Format date for X axis
  const formatXAxis = (date: string) => {
    // Append T12:00:00 to avoid timezone shift
    const d = new Date(date + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "short" });
  };

  // Get latest news sentiment for summary
  const latestNewsSentiment = chartData.length > 0 ? chartData[chartData.length - 1].newsRaw : null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (fgError || !fearGreedData?.dates?.length) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        Unable to load sentiment data
      </div>
    );
  }

  // Custom tooltip to show both metrics
  const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; dataKey: string; payload: { newsRaw?: number; label?: string } }>; label?: string }) => {
    if (!active || !payload?.length) return null;
    const dateStr = typeof label === "string"
      ? new Date(label + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
      : "";
    const fgValue = payload.find(p => p.dataKey === "score");
    const newsValue = payload.find(p => p.dataKey === "newsSentiment");

    return (
      <div className="bg-surface border border-border rounded-lg p-2 text-xs shadow-lg">
        <div className="font-medium mb-1">{dateStr}</div>
        {fgValue && (
          <div className="flex justify-between gap-4">
            <span className="text-purple-400">Fear & Greed:</span>
            <span className="font-semibold">{fgValue.value} ({fgValue.payload.label})</span>
          </div>
        )}
        {newsValue && newsValue.payload.newsRaw !== null && newsValue.payload.newsRaw !== undefined && (
          <div className="flex justify-between gap-4">
            <span className="text-cyan-400">News Sentiment:</span>
            <span className="font-semibold">{newsValue.payload.newsRaw > 0 ? "+" : ""}{(newsValue.payload.newsRaw * 100).toFixed(0)}%</span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Market Sentiment</h3>
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
      </div>

      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
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
            <Tooltip content={<CustomTooltip />} />
            <defs>
              <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
              </linearGradient>
            </defs>
            {/* Fear & Greed area */}
            <Area
              type="monotone"
              dataKey="score"
              stroke="#8B5CF6"
              strokeWidth={2}
              fill="url(#sentimentGradient)"
              name="Fear & Greed"
            />
            {/* News Sentiment line overlay */}
            <Line
              type="monotone"
              dataKey="newsSentiment"
              stroke="#22d3ee"
              strokeWidth={2}
              dot={false}
              connectNulls
              name="News Sentiment"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend and summary row */}
      <div className="flex items-center justify-between text-xs text-text-muted">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-purple-500 rounded"></span>
            <span>Fear & Greed: <span className="font-semibold text-text">{currentScore}</span></span>
          </span>
          {latestNewsSentiment !== null && latestNewsSentiment !== undefined && (
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-cyan-400 rounded"></span>
              <span>News: <span className="font-semibold text-text">{latestNewsSentiment > 0 ? "+" : ""}{(latestNewsSentiment * 100).toFixed(0)}%</span></span>
            </span>
          )}
        </div>
        <span>
          Range: {minScore.toFixed(0)}–{maxScore.toFixed(0)}
        </span>
      </div>
    </div>
  );
}
