"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";
import { ArrowUpIcon, ArrowDownIcon, TrendingUp, TrendingDown } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";

// ============================================================================
// Types
// ============================================================================

interface PaperTrade {
  id: string;
  symbol: string;
  entryPrice: number;
  currentPrice?: number;
  exitPrice?: number;
  returnPct?: number;
  status: "open" | "closed_win" | "closed_loss" | "stopped_out";
  entryDate: string;
  exitDate?: string;
  signalType?: string;
  signalStrength?: number;
  style?: string;
}

interface PaperTradePerformanceProps {
  trades: PaperTrade[];
  isLoading?: boolean;
}

interface PerformanceMetrics {
  totalTrades: number;
  openTrades: number;
  closedTrades: number;
  winRate: number;
  avgReturn: number;
  totalReturn: number;
  bestTrade: number;
  worstTrade: number;
}

interface FeatureContribution {
  feature: string;
  winRate: number;
  avgReturn: number;
  count: number;
}

// ============================================================================
// Metrics Calculation
// ============================================================================

function calculateMetrics(trades: PaperTrade[]): PerformanceMetrics {
  const openTrades = trades.filter((t) => t.status === "open");
  const closedTrades = trades.filter((t) => t.status !== "open");
  const wins = closedTrades.filter((t) => (t.returnPct ?? 0) > 0);

  const returns = closedTrades.map((t) => t.returnPct ?? 0);
  const avgReturn = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
  const totalReturn = returns.reduce((a, b) => a + b, 0);

  return {
    totalTrades: trades.length,
    openTrades: openTrades.length,
    closedTrades: closedTrades.length,
    winRate: closedTrades.length > 0 ? (wins.length / closedTrades.length) * 100 : 0,
    avgReturn,
    totalReturn,
    bestTrade: returns.length > 0 ? Math.max(...returns) : 0,
    worstTrade: returns.length > 0 ? Math.min(...returns) : 0,
  };
}

function calculateFeatureContributions(trades: PaperTrade[]): FeatureContribution[] {
  const closedTrades = trades.filter((t) => t.status !== "open");

  // Group by signal type
  const signalGroups = closedTrades.reduce((acc, trade) => {
    const signal = trade.signalType || "UNKNOWN";
    if (!acc[signal]) {
      acc[signal] = [];
    }
    acc[signal].push(trade);
    return acc;
  }, {} as Record<string, PaperTrade[]>);

  // Calculate metrics per signal
  const contributions: FeatureContribution[] = Object.entries(signalGroups).map(([signal, trades]) => {
    const wins = trades.filter((t) => (t.returnPct ?? 0) > 0);
    const returns = trades.map((t) => t.returnPct ?? 0);
    const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;

    return {
      feature: signal,
      winRate: (wins.length / trades.length) * 100,
      avgReturn,
      count: trades.length,
    };
  });

  return contributions.sort((a, b) => b.avgReturn - a.avgReturn);
}

// ============================================================================
// Metric Card Component
// ============================================================================

interface MetricCardProps {
  label: string;
  value: number | string;
  format?: "percent" | "currency" | "number";
  trend?: "up" | "down" | "neutral";
}

function MetricCard({ label, value, format: formatType = "number", trend }: MetricCardProps) {
  let formattedValue = "";
  if (formatType === "percent") {
    const numValue = typeof value === "number" ? value : 0;
    formattedValue = `${numValue >= 0 ? "+" : ""}${numValue.toFixed(2)}%`;
  } else if (formatType === "currency") {
    const numValue = typeof value === "number" ? value : 0;
    formattedValue = `$${numValue.toFixed(2)}`;
  } else {
    formattedValue = String(value);
  }

  const trendIcon =
    trend === "up" ? (
      <ArrowUpIcon className="h-4 w-4 text-gain" />
    ) : trend === "down" ? (
      <ArrowDownIcon className="h-4 w-4 text-loss" />
    ) : null;

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-medium text-text-muted mb-1">{label}</div>
          <div className="text-2xl font-bold text-text">{formattedValue}</div>
        </div>
        {trendIcon}
      </div>
    </Card>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function PaperTradePerformance({ trades, isLoading }: PaperTradePerformanceProps) {
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-4 h-24 animate-pulse bg-surface-muted/60" />
          ))}
        </div>
      </div>
    );
  }

  if (trades.length === 0) {
    return (
      <Card className="p-8 text-center">
        <TrendingUp className="h-12 w-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted">No paper trades yet</p>
      </Card>
    );
  }

  const metrics = calculateMetrics(trades);
  const featureContributions = calculateFeatureContributions(trades);

  // Cumulative return chart data
  const closedTrades = trades
    .filter((t) => t.status !== "open" && t.exitDate)
    .sort((a, b) => new Date(a.exitDate!).getTime() - new Date(b.exitDate!).getTime());

  let cumulative = 0;
  const chartData = closedTrades.map((trade) => {
    cumulative += trade.returnPct ?? 0;
    return {
      date: trade.exitDate!,
      return: cumulative,
    };
  });

  return (
    <div className="space-y-6">
      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Trades"
          value={metrics.totalTrades}
          trend="neutral"
        />
        <MetricCard
          label="Win Rate"
          value={metrics.winRate}
          format="percent"
          trend={metrics.winRate >= 50 ? "up" : "down"}
        />
        <MetricCard
          label="Avg Return"
          value={metrics.avgReturn}
          format="percent"
          trend={metrics.avgReturn >= 0 ? "up" : "down"}
        />
        <MetricCard
          label="Total Return"
          value={metrics.totalReturn}
          format="percent"
          trend={metrics.totalReturn >= 0 ? "up" : "down"}
        />
      </div>

      {/* Cumulative Return Chart */}
      {chartData.length > 0 && (
        <Card className="p-6">
          <h3 className="text-sm font-semibold text-text mb-4">Cumulative Returns</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="date"
                stroke="var(--text-muted)"
                fontSize={12}
                tickFormatter={(value) => format(new Date(value), "MMM d")}
              />
              <YAxis
                stroke="var(--text-muted)"
                fontSize={12}
                tickFormatter={(value) => `${value.toFixed(0)}%`}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  return (
                    <div className="bg-surface border border-border rounded-lg p-3 shadow-lg">
                      <p className="text-xs text-text-muted mb-1">
                        {format(new Date(payload[0].payload.date), "MMM d, yyyy")}
                      </p>
                      <p className="text-sm font-medium text-text">
                        Return: {(payload[0].value as number).toFixed(2)}%
                      </p>
                    </div>
                  );
                }}
              />
              <Line
                type="monotone"
                dataKey="return"
                stroke="var(--gain)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Feature Contributions */}
      {featureContributions.length > 0 && (
        <Card className="p-6">
          <h3 className="text-sm font-semibold text-text mb-4">Signal Performance</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={featureContributions}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="feature"
                stroke="var(--text-muted)"
                fontSize={12}
              />
              <YAxis
                stroke="var(--text-muted)"
                fontSize={12}
                tickFormatter={(value) => `${value.toFixed(0)}%`}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const data = payload[0].payload as FeatureContribution;
                  return (
                    <div className="bg-surface border border-border rounded-lg p-3 shadow-lg">
                      <p className="text-xs font-semibold text-text mb-2">{data.feature}</p>
                      <p className="text-xs text-text-muted">Win Rate: {data.winRate.toFixed(1)}%</p>
                      <p className="text-xs text-text-muted">Avg Return: {data.avgReturn.toFixed(2)}%</p>
                      <p className="text-xs text-text-muted">Trades: {data.count}</p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="avgReturn" fill="var(--gain)" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
