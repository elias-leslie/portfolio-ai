"use client";

import {
  BarChart,
  Bar,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
  ReferenceLine,
} from "recharts";
import { Card } from "@/components/ui/card";
import { SectionCard } from "@/components/shared/SectionCard";

interface Trade {
  pnl_pct: string | number | null;
}

interface TradeDistributionChartProps {
  trades: Trade[];
  profitFactor: number | null;
}

interface BinData {
  range: string;
  count: number;
  isWin: boolean;
  minPct: number;
  maxPct: number;
}

function createDistributionBins(trades: Trade[]): BinData[] {
  // Parse pnl_pct values (filter out null)
  const pnlValues = trades
    .filter((t) => t.pnl_pct !== null)
    .map((t) =>
      typeof t.pnl_pct === "string" ? parseFloat(t.pnl_pct) : (t.pnl_pct as number)
    );

  // Define bins: -30%, -20%, -10%, -5%, 0%, +5%, +10%, +20%, +30%
  const binEdges = [-30, -20, -10, -5, 0, 5, 10, 20, 30];
  const bins: BinData[] = [];

  // Create bins for losses (negative values)
  for (let i = 0; i < binEdges.length - 1; i++) {
    const minPct = binEdges[i];
    const maxPct = binEdges[i + 1];
    const count = pnlValues.filter((v) => v >= minPct && v < maxPct).length;

    if (count > 0 || (minPct >= -20 && maxPct <= 20)) {
      // Always show -20% to +20% range
      bins.push({
        range: `${minPct >= 0 ? "+" : ""}${minPct}%`,
        count,
        isWin: minPct >= 0,
        minPct,
        maxPct,
      });
    }
  }

  // Add overflow bins for extreme values
  const belowMin = pnlValues.filter((v) => v < -30).length;
  const aboveMax = pnlValues.filter((v) => v >= 30).length;

  if (belowMin > 0) {
    bins.unshift({
      range: "<-30%",
      count: belowMin,
      isWin: false,
      minPct: -100,
      maxPct: -30,
    });
  }

  if (aboveMax > 0) {
    bins.push({
      range: ">+30%",
      count: aboveMax,
      isWin: true,
      minPct: 30,
      maxPct: 100,
    });
  }

  return bins;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: BinData }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload;
  return (
    <div className="bg-surface border border-border rounded-lg p-3 shadow-lg">
      <p className="text-sm font-medium text-text">
        {data.range} to {data.maxPct >= 0 ? "+" : ""}
        {data.maxPct}%
      </p>
      <p className="text-xs text-text-muted mt-1">
        {data.count} trade{data.count !== 1 ? "s" : ""}
      </p>
    </div>
  );
}

export function TradeDistributionChart({
  trades,
  profitFactor,
}: TradeDistributionChartProps) {
  if (!trades || trades.length === 0) {
    return null;
  }

  // Calculate statistics from trades (filter out null values)
  const pnlValues = trades
    .filter((t) => t.pnl_pct !== null)
    .map((t) =>
      typeof t.pnl_pct === "string" ? parseFloat(t.pnl_pct) : (t.pnl_pct as number)
    );

  const winningTrades = pnlValues.filter((v) => v >= 0);
  const losingTrades = pnlValues.filter((v) => v < 0);

  const numWins = winningTrades.length;
  const numLosses = losingTrades.length;

  const avgWin =
    winningTrades.length > 0
      ? winningTrades.reduce((a, b) => a + b, 0) / winningTrades.length
      : null;

  const avgLoss =
    losingTrades.length > 0
      ? losingTrades.reduce((a, b) => a + b, 0) / losingTrades.length
      : null;

  const bins = createDistributionBins(trades);
  const winRate =
    numWins + numLosses > 0
      ? ((numWins / (numWins + numLosses)) * 100).toFixed(1)
      : "0";

  return (
    <SectionCard
      variant="surface"
      title="Trade Distribution"
      description="P&L distribution histogram with win/loss breakdown"
    >
      {/* Key Metrics Row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-6">
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">
            Avg Win
          </div>
          <div className="text-lg font-bold text-gain">
            {avgWin !== null ? `+${avgWin.toFixed(2)}%` : "—"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">
            Avg Loss
          </div>
          <div className="text-lg font-bold text-loss">
            {avgLoss !== null ? `-${Math.abs(avgLoss).toFixed(2)}%` : "—"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">
            Profit Factor
          </div>
          <div className="text-lg font-bold text-text">
            {profitFactor !== null ? profitFactor.toFixed(2) : "—"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">
            Win/Loss
          </div>
          <div className="text-lg font-bold text-text">
            <span className="text-gain">{numWins}</span>
            <span className="text-text-muted">/</span>
            <span className="text-loss">{numLosses}</span>
            <span className="text-xs text-text-muted ml-2">({winRate}%)</span>
          </div>
        </Card>
      </div>

      {/* Histogram Chart */}
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={bins}
          margin={{ top: 20, right: 30, bottom: 20, left: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="range"
            tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
            angle={-45}
            textAnchor="end"
            height={60}
          />
          <YAxis
            tick={{ fontSize: 12, fill: "var(--color-text-muted)" }}
            label={{
              value: "# Trades",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 12, fill: "var(--color-text-muted)" },
            }}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine x="+0%" stroke="var(--color-text-muted)" strokeDasharray="5 5" />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {bins.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.isWin ? "var(--color-gain)" : "var(--color-loss)"}
                fillOpacity={0.8}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <p className="mt-4 text-xs text-text-muted text-center">
        Green bars = winning trades • Red bars = losing trades
      </p>
    </SectionCard>
  );
}
