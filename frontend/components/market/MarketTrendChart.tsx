/**
 * MarketTrendChart Component
 *
 * Small sparkline chart showing 30-day market trends.
 * Displays Fear & Greed scores and optionally Market Health scores.
 */

"use client";

import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { format } from "date-fns";

export interface MarketTrendData {
  dates: string[];
  fear_greed_scores: number[];
  market_health_scores: number[];
}

interface MarketTrendChartProps {
  data: MarketTrendData;
  height?: number;
}

interface ChartDataPoint {
  date: string;
  fearGreed: number;
  marketHealth?: number;
}

interface TooltipPayload {
  payload: ChartDataPoint;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
}

// Custom tooltip component (outside main component to avoid recreation)
function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload;
  const dateObj = new Date(data.date);

  return (
    <div className="bg-surface border border-border rounded-lg p-3 shadow-lg">
      <p className="text-xs text-text-muted mb-2">
        {format(dateObj, "MMM d, yyyy")}
      </p>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--color-gain)' }} />
          <span className="text-xs font-medium text-text">
            Fear & Greed: {data.fearGreed.toFixed(0)}
          </span>
        </div>
        {data.marketHealth !== undefined && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--color-chart-3)' }} />
            <span className="text-xs font-medium text-text">
              Market Health: {data.marketHealth.toFixed(0)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export function MarketTrendChart({ data, height = 60 }: MarketTrendChartProps) {
  // Transform data for recharts
  const chartData: ChartDataPoint[] = data.dates.map((date, index) => ({
    date,
    fearGreed: data.fear_greed_scores[index],
    marketHealth: data.market_health_scores[index] || undefined,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
        {/* Hidden X-axis for cleaner look */}
        <XAxis dataKey="date" hide />

        {/* Tooltip */}
        <Tooltip content={<CustomTooltip />} />

        {/* Fear & Greed line (primary) - using gain color for visibility */}
        <Line
          type="monotone"
          dataKey="fearGreed"
          stroke="var(--color-gain)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />

        {/* Market Health line (secondary, if available) - using chart color */}
        {data.market_health_scores.length > 0 && (
          <Line
            type="monotone"
            dataKey="marketHealth"
            stroke="var(--color-chart-3)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
