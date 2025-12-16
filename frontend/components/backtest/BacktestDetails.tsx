"use client";

import { useState } from "react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  ColumnDef,
  SortingState,
} from "@tanstack/react-table";
import { formatDate } from "@/lib/utils";
import { ArrowUpIcon, ArrowDownIcon, TrendingUp, Loader2, BarChart2 } from "lucide-react";

import { SectionCard } from "@/components/shared/SectionCard";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import {
  useBacktestRun,
  useBacktestEquity,
  useCompareBacktests,
  useMonteCarloSimulation,
} from "@/lib/hooks/useBacktestUI";
import type { BacktestEquity, BacktestTrade, BacktestComparisonResponse, RunMetrics, MonteCarloResponse } from "@/lib/api/backtest-ui";
import { TradeDistributionChart } from "./TradeDistributionChart";
import { MonthlyReturnsHeatmap } from "./MonthlyReturnsHeatmap";

// ============================================================================
// Types
// ============================================================================

interface BacktestDetailsProps {
  runId: string | null;
  comparisonMode: boolean;
  comparisonRunIds: string[];
}

interface ChartDataPoint {
  date: string;
  [key: string]: string | number;
}

interface TooltipPayload {
  payload: ChartDataPoint;
  name?: string;
  value?: string | number;
  color?: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
}

// ============================================================================
// Constants
// ============================================================================

const LINE_COLORS = [
  "var(--color-gain)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
];

// ============================================================================
// Custom Tooltip
// ============================================================================

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload;
  const dateObj = new Date(data.date);

  return (
    <div className="bg-surface border border-border rounded-lg p-3 shadow-lg">
      <p className="text-xs text-text-muted mb-2">
        {formatDate(dateObj.toISOString())}
      </p>
      <div className="space-y-1">
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: entry.color || LINE_COLORS[index] }}
            />
            <span className="text-xs font-medium text-text">
              {entry.name}: {typeof entry.value === "number" ? entry.value.toFixed(2) : entry.value}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Metric Card Component
// ============================================================================

interface MetricCardProps {
  label: string;
  value: number | null;
  format?: "percent" | "currency" | "number";
  isPositive?: boolean;
}

function MetricCard({ label, value, format: formatType = "number", isPositive }: MetricCardProps) {
  if (value === null || value === undefined) {
    return (
      <Card className="p-4">
        <div className="text-xs font-medium text-text-muted mb-2">{label}</div>
        <div className="text-text-muted">—</div>
      </Card>
    );
  }

  let formattedValue = "";
  if (formatType === "percent") {
    formattedValue = `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  } else if (formatType === "currency") {
    formattedValue = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  } else {
    formattedValue = value.toFixed(2);
  }

  const shouldDetermineColor = isPositive === undefined;
  const isGain = shouldDetermineColor ? value >= 0 : isPositive;
  const colorClass = isGain ? "text-gain" : "text-loss";
  const iconClass = "h-4 w-4";

  return (
    <Card className="p-4">
      <div className="text-xs font-medium text-text-muted mb-2">{label}</div>
      <div className="flex items-center gap-2">
        <div className={`${colorClass} text-lg font-bold`}>{formattedValue}</div>
        {shouldDetermineColor && (
          <div className={colorClass}>
            {isGain ? (
              <ArrowUpIcon className={iconClass} />
            ) : (
              <ArrowDownIcon className={iconClass} />
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function BacktestDetails({
  runId,
  comparisonMode,
  comparisonRunIds,
}: BacktestDetailsProps) {
  const [tradeSorting, setTradeSorting] = useState<SortingState>([]);
  const [monteCarloData, setMonteCarloData] = useState<MonteCarloResponse | null>(null);

  // Fetch single run data
  const { data: runData, isLoading: runLoading } = useBacktestRun(
    runId || "",
    { enabled: !!runId && !comparisonMode }
  );

  // Fetch equity curve for single run
  const { data: equityData, isLoading: equityLoading } = useBacktestEquity(
    runId || "",
    { enabled: !!runId && !comparisonMode }
  );

  // Fetch comparison data
  const { data: comparisonData, isLoading: comparisonLoading } = useCompareBacktests(
    comparisonRunIds,
    { enabled: comparisonMode && comparisonRunIds.length >= 2 }
  );

  // Monte Carlo simulation mutation
  const monteCarloMutation = useMonteCarloSimulation(runId || "");

  // Handle Monte Carlo run
  const handleRunMonteCarlo = async () => {
    setMonteCarloData(null);
    const result = await monteCarloMutation.mutateAsync({ numSimulations: 1000 });
    setMonteCarloData(result);
  };

  // Determine loading state
  const isLoading = comparisonMode ? comparisonLoading : runLoading || equityLoading;

  // Handle no selection
  if (!runId && !comparisonMode) {
    return (
      <SectionCard variant="surface" padding="lg">
        <div className="flex flex-col items-center justify-center py-12">
          <TrendingUp className="h-12 w-12 text-text-muted/50 mb-4" />
          <p className="text-center text-text-muted">
            Select a backtest run to view details and analysis
          </p>
        </div>
      </SectionCard>
    );
  }

  // Handle comparison mode without selections
  if (comparisonMode && comparisonRunIds.length < 2) {
    return (
      <SectionCard variant="surface" padding="lg">
        <div className="flex flex-col items-center justify-center py-12">
          <TrendingUp className="h-12 w-12 text-text-muted/50 mb-4" />
          <p className="text-center text-text-muted">
            Select 2-5 backtest runs to compare equity curves
          </p>
        </div>
      </SectionCard>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <SectionCard variant="surface">
          <div className="h-80 bg-surface-muted/60 rounded-lg animate-pulse" />
        </SectionCard>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-24 bg-surface-muted/60 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  // Comparison mode rendering
  if (comparisonMode && comparisonData) {
    // Get symbol names for legend
    const symbolMap: Record<string, string> = {};
    comparisonData.metrics.forEach((m) => {
      symbolMap[m.runId] = m.symbol;
    });

    return (
      <div className="space-y-6">
        {/* Equity Curve Comparison Chart */}
        <SectionCard
          variant="surface"
          title="Equity Curve Comparison"
          description="Normalized returns overlay (starting at 0%)"
        >
          <ResponsiveContainer width="100%" height={400}>
            <LineChart
              data={transformComparisonData(comparisonData)}
              margin={{ top: 5, right: 30, bottom: 5, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12, fill: "var(--color-text-muted)" }}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "var(--color-text-muted)" }}
                label={{ value: "Return %", angle: -90, position: "insideLeft" }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              {comparisonRunIds.map((runId, index) => (
                <Line
                  key={runId}
                  type="monotone"
                  dataKey={`return_${runId}`}
                  stroke={LINE_COLORS[index % LINE_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6 }}
                  name={symbolMap[runId] || `Run ${index + 1}`}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </SectionCard>

        {/* Metrics Comparison Table */}
        <SectionCard
          variant="surface"
          title="Performance Metrics"
          description="Side-by-side comparison with rankings"
        >
          <MetricsComparisonTable metrics={comparisonData.metrics} />
        </SectionCard>

        {/* Correlation Matrix (if available) */}
        {comparisonData.correlationMatrix && (
          <SectionCard
            variant="surface"
            title="Strategy Correlation"
            description="Return correlation between strategies"
          >
            <div className="rounded-md border border-border bg-surface/40 overflow-x-auto p-4">
              <div className="grid gap-2" style={{ gridTemplateColumns: `auto repeat(${Object.keys(comparisonData.correlationMatrix).length}, 1fr)` }}>
                {/* Header row */}
                <div className="font-medium text-text-muted"></div>
                {Object.keys(comparisonData.correlationMatrix).map((runId) => (
                  <div key={runId} className="text-center text-xs font-medium text-text-muted">
                    {symbolMap[runId] || runId.slice(0, 8)}
                  </div>
                ))}
                {/* Data rows */}
                {Object.entries(comparisonData.correlationMatrix).map(([rowId, correlations]) => (
                  <>
                    <div key={`label-${rowId}`} className="text-xs font-medium text-text-muted">
                      {symbolMap[rowId] || rowId.slice(0, 8)}
                    </div>
                    {Object.entries(correlations).map(([colId, corr]) => (
                      <div
                        key={`${rowId}-${colId}`}
                        className={cn(
                          "text-center text-xs font-medium rounded px-2 py-1",
                          corr >= 0.7 ? "bg-loss/20 text-loss" :
                          corr >= 0.4 ? "bg-warning/20 text-warning" :
                          "bg-gain/20 text-gain"
                        )}
                      >
                        {corr.toFixed(2)}
                      </div>
                    ))}
                  </>
                ))}
              </div>
              <p className="mt-4 text-xs text-text-muted">
                Low correlation (&lt;0.4) = good diversification • High correlation (&gt;0.7) = similar strategies
              </p>
            </div>
          </SectionCard>
        )}

        <div className="rounded-lg border border-border bg-surface/40 p-4 text-sm text-text-muted">
          <p>Comparing {comparisonRunIds.length} backtest runs</p>
        </div>
      </div>
    );
  }

  // Single run rendering
  if (!runData) {
    return (
      <SectionCard variant="surface" padding="lg">
        <div className="flex flex-col items-center justify-center py-12">
          <p className="text-center text-text-muted">
            Backtest not found or still loading
          </p>
        </div>
      </SectionCard>
    );
  }

  const run = runData.run;
  const trades = runData.trades || [];
  const equity = equityData || [];

  // Transform equity data for chart - calculate cumulative return from equity
  const initialEquity = equity.length > 0 ? parseFloat(String(equity[0].equity)) : 100000;
  const chartData = equity.map((point) => ({
    date: point.date,
    return: ((parseFloat(String(point.equity)) - initialEquity) / initialEquity) * 100,
  }));

  // Format metrics - convert string to number if needed
  const formatPercent = (value: string | number | null): number | null => {
    if (value === null) return null;
    return typeof value === "string" ? parseFloat(value) : value;
  };

  const formatCurrency = (value: string | number | null): number | null => {
    if (value === null) return null;
    return typeof value === "string" ? parseFloat(value) : value;
  };

  return (
    <div className="space-y-6">
      {/* Run Header */}
      <SectionCard variant="surface" padding="md">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-2xl font-bold text-text">{run.symbol}</h2>
            <p className="text-sm text-text-muted mt-1">
              {formatDate(run.startDate)} →{" "}
              {formatDate(run.endDate)}
            </p>
            {run.createdAt && (
              <p className="text-xs text-text-muted mt-0.5 opacity-70">
                Run created {formatDate(run.createdAt)}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Badge
              variant={
                run.status === "completed"
                  ? "secondary"
                  : run.status === "failed"
                  ? "destructive"
                  : "default"
              }
            >
              {run.status}
            </Badge>
            {run.totalReturnPct !== null && (
              <div className="text-right">
                <div
                  className={cn(
                    "text-2xl font-bold",
                    parseFloat(String(run.totalReturnPct)) >= 0 ? "text-gain" : "text-loss"
                  )}
                >
                  {parseFloat(String(run.totalReturnPct)) >= 0 ? "+" : ""}
                  {parseFloat(String(run.totalReturnPct)).toFixed(2)}%
                </div>
                <p className="text-xs text-text-muted">Total Return</p>
              </div>
            )}
          </div>
        </div>
      </SectionCard>

      {/* Equity Curve Chart */}
      {chartData.length > 0 && (
        <SectionCard
          variant="surface"
          title="Equity Curve"
          description="Portfolio value over time"
        >
          <ResponsiveContainer width="100%" height={400}>
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 30, bottom: 5, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12, fill: "var(--color-text-muted)" }}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "var(--color-text-muted)" }}
                label={{ value: "Return %", angle: -90, position: "insideLeft" }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="return"
                stroke="var(--color-gain)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </SectionCard>
      )}

      {/* Metrics Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <MetricCard
          label="Total Return"
          value={formatPercent(run.totalReturnPct)}
          format="percent"
        />
        <MetricCard
          label="Sharpe Ratio"
          value={run.sharpeRatio ? parseFloat(run.sharpeRatio.toString()) : null}
          format="number"
        />
        <MetricCard
          label="Win Rate"
          value={formatPercent(run.winRate)}
          format="percent"
          isPositive
        />
        <MetricCard
          label="Max Drawdown"
          value={
            run.maxDrawdownPct
              ? -parseFloat(run.maxDrawdownPct.toString())
              : null
          }
          format="percent"
          isPositive={false}
        />
        <MetricCard
          label="Profit Factor"
          value={run.profitFactor ? parseFloat(run.profitFactor.toString()) : null}
          format="number"
        />
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Num Trades</div>
          <div className="text-2xl font-bold text-text">{run.numTrades || 0}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Initial Capital</div>
          <div className="text-sm font-bold text-text">
            {new Intl.NumberFormat("en-US", {
              style: "currency",
              currency: "USD",
              minimumFractionDigits: 0,
            }).format(parseFloat(run.initialCapital.toString()))}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Final Equity</div>
          <div className="text-sm font-bold text-text">
            {run.finalEquity
              ? new Intl.NumberFormat("en-US", {
                  style: "currency",
                  currency: "USD",
                  minimumFractionDigits: 0,
                }).format(parseFloat(run.finalEquity.toString()))
              : "—"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Strategy</div>
          <div className="text-sm font-bold text-text capitalize">{run.strategyName}</div>
        </Card>
      </div>

      {/* Trade Distribution Chart */}
      {trades.length > 0 && (
        <TradeDistributionChart
          trades={trades}
          profitFactor={run.profitFactor ? parseFloat(String(run.profitFactor)) : null}
        />
      )}

      {/* Monthly Returns Heatmap */}
      {equity.length > 0 && <MonthlyReturnsHeatmap equityCurve={equity} />}

      {/* Trades Table */}
      {trades.length > 0 && (
        <SectionCard
          variant="surface"
          title="Trade History"
          description={`${trades.length} trades executed`}
        >
          <TradesTable trades={trades} sorting={tradeSorting} onSortingChange={setTradeSorting} />
        </SectionCard>
      )}

      {/* No trades state */}
      {trades.length === 0 && (
        <SectionCard
          variant="surface"
          title="Trade History"
          description="No trades executed"
        >
          <div className="py-8 text-center text-text-muted">
            <p>No trades were executed during this backtest period.</p>
          </div>
        </SectionCard>
      )}

      {/* Monte Carlo Simulation Section */}
      {trades.length > 0 && run.status === "completed" && (
        <SectionCard
          variant="surface"
          title="Monte Carlo Simulation"
          description="Stress test strategy with randomized scenarios"
        >
          {!monteCarloData && !monteCarloMutation.isPending && (
            <div className="flex flex-col items-center justify-center py-8">
              <BarChart2 className="h-12 w-12 text-text-muted/50 mb-4" />
              <p className="text-sm text-text-muted mb-4">
                Run 1,000 simulations to estimate probability distribution of returns
              </p>
              <Button onClick={handleRunMonteCarlo} variant="outline">
                <BarChart2 className="mr-2 h-4 w-4" />
                Run Monte Carlo
              </Button>
            </div>
          )}

          {monteCarloMutation.isPending && (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-text-muted mb-4" />
              <p className="text-sm text-text-muted">Running simulations...</p>
            </div>
          )}

          {monteCarloMutation.isError && (
            <div className="py-8 text-center">
              <p className="text-sm text-loss mb-4">
                Simulation failed: {String(monteCarloMutation.error)}
              </p>
              <Button onClick={handleRunMonteCarlo} variant="outline" size="sm">
                Try Again
              </Button>
            </div>
          )}

          {monteCarloData && <MonteCarloResults data={monteCarloData} />}
        </SectionCard>
      )}
    </div>
  );
}

// ============================================================================
// Trades Table Component
// ============================================================================

interface TradesTableProps {
  trades: BacktestTrade[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
}

function TradesTable({ trades, sorting, onSortingChange }: TradesTableProps) {
  // Using standard formatDate from @/lib/utils

  const formatCurrency = (value: number | undefined) => {
    if (value === undefined || value === null) return "—";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number | undefined) => {
    if (value === undefined || value === null) return "—";
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  };

  const columns: ColumnDef<BacktestTrade>[] = [
    {
      accessorKey: "entry_date",
      header: "Entry Date",
      cell: ({ row }) => formatDate(row.original.entryDate as any),
    },
    {
      accessorKey: "entry_price",
      header: "Entry Price",
      cell: ({ row }) => formatCurrency(parseFloat(row.original.entryPrice.toString())),
    },
    {
      accessorKey: "exit_date",
      header: "Exit Date",
      cell: ({ row }) => formatDate(row.original.exitDate as any),
    },
    {
      accessorKey: "exit_price",
      header: "Exit Price",
      cell: ({ row }) =>
        row.original.exitPrice
          ? formatCurrency(parseFloat(row.original.exitPrice.toString()))
          : "—",
    },
    {
      accessorKey: "shares",
      header: "Shares",
      cell: ({ row }) => row.getValue("shares"),
    },
    {
      accessorKey: "pnl_pct",
      header: "P&L %",
      cell: ({ row }) => {
        const pnl = row.original.pnlPct
          ? parseFloat(row.original.pnlPct.toString())
          : null;
        return pnl !== null ? (
          <span className={pnl >= 0 ? "text-gain font-medium" : "text-loss font-medium"}>
            {formatPercent(pnl)}
          </span>
        ) : (
          "—"
        );
      },
    },
    {
      accessorKey: "exit_reason",
      header: "Exit Reason",
      cell: ({ row }) => {
        const reason = row.getValue("exit_reason") as string | null;
        if (!reason) return "—";
        return (
          <Badge variant="outline" className="text-xs">
            {reason}
          </Badge>
        );
      },
    },
  ];

  const table = useReactTable({
    data: trades,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: (updater) => {
      if (typeof updater === "function") {
        onSortingChange(updater(sorting));
      } else {
        onSortingChange(updater);
      }
    },
    state: {
      sorting,
    },
  });

  return (
    <div className="rounded-md border border-border bg-surface/40 overflow-x-auto">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id}>
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => {
            const pnl = row.original.pnlPct
              ? parseFloat(row.original.pnlPct.toString())
              : 0;
            const bgClass =
              pnl >= 0
                ? "bg-green-50/30 dark:bg-green-950/10 hover:bg-green-50/50 dark:hover:bg-green-950/20"
                : "bg-red-50/30 dark:bg-red-950/10 hover:bg-red-50/50 dark:hover:bg-red-950/20";

            return (
              <TableRow key={row.id} className={bgClass}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Transform comparison data from API format to chart format
 * Converts multiple runs' equity curves into a single chart dataset
 */
function transformComparisonData(
  comparisonData: BacktestComparisonResponse
): ChartDataPoint[] {
  const dateMap = new Map<string, ChartDataPoint>();

  // Iterate through each run's equity curve
  Object.entries(comparisonData.equityCurves).forEach(([runId, equityPoints]) => {
    equityPoints.forEach((point) => {
      const dateStr = point.date;
      if (!dateMap.has(dateStr)) {
        dateMap.set(dateStr, { date: dateStr });
      }

      const chartPoint = dateMap.get(dateStr)!;
      chartPoint[`return_${runId}`] = parseFloat(point.cumulativeReturnPct.toString());
    });
  });

  // Convert map to sorted array
  return Array.from(dateMap.values()).sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );
}

/**
 * Render a rank badge (1 = gold, 2 = silver, 3 = bronze)
 */
function RankBadge({ rank }: { rank: number | null }) {
  if (rank === null) return <span className="text-text-muted">—</span>;

  const variants: Record<number, "default" | "secondary" | "outline"> = {
    1: "default",
    2: "secondary",
    3: "outline",
  };

  return (
    <Badge variant={variants[rank] || "outline"} className="text-xs font-medium">
      #{rank}
    </Badge>
  );
}

/**
 * Metrics comparison table component
 */
function MetricsComparisonTable({ metrics }: { metrics: RunMetrics[] }) {
  const formatPercent = (value: string | null) => {
    if (value === null) return "—";
    const num = parseFloat(value);
    return `${num >= 0 ? "+" : ""}${num.toFixed(2)}%`;
  };

  const formatNumber = (value: string | null) => {
    if (value === null) return "—";
    return parseFloat(value).toFixed(2);
  };

  return (
    <div className="rounded-md border border-border bg-surface/40 overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Symbol</TableHead>
            <TableHead>Return</TableHead>
            <TableHead>Rank</TableHead>
            <TableHead>Sharpe</TableHead>
            <TableHead>Rank</TableHead>
            <TableHead>Drawdown</TableHead>
            <TableHead>Rank</TableHead>
            <TableHead>Win Rate</TableHead>
            <TableHead>Trades</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {metrics.map((m) => (
            <TableRow key={m.runId}>
              <TableCell className="font-medium">{m.symbol}</TableCell>
              <TableCell className={cn(
                parseFloat(m.totalReturnPct || "0") >= 0 ? "text-gain" : "text-loss",
                "font-medium"
              )}>
                {formatPercent(m.totalReturnPct)}
              </TableCell>
              <TableCell><RankBadge rank={m.returnRank} /></TableCell>
              <TableCell>{formatNumber(m.sharpeRatio)}</TableCell>
              <TableCell><RankBadge rank={m.sharpeRank} /></TableCell>
              <TableCell className="text-loss">{formatPercent(m.maxDrawdownPct)}</TableCell>
              <TableCell><RankBadge rank={m.drawdownRank} /></TableCell>
              <TableCell>{formatPercent(m.winRate)}</TableCell>
              <TableCell>{m.numTrades ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/**
 * Monte Carlo results section component
 */
function MonteCarloResults({ data }: { data: MonteCarloResponse }) {
  const stats = data.statistics;

  return (
    <div className="space-y-6">
      {/* Key Statistics Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Median Return</div>
          <div className={cn(
            "text-lg font-bold",
            stats.percentile50 >= 0 ? "text-gain" : "text-loss"
          )}>
            {stats.percentile50 >= 0 ? "+" : ""}{stats.percentile50.toFixed(2)}%
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">95% Confidence</div>
          <div className="text-sm font-medium text-text">
            {stats.percentile5.toFixed(1)}% to {stats.percentile95.toFixed(1)}%
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Prob. of Loss</div>
          <div className={cn(
            "text-lg font-bold",
            stats.probabilityOfLoss <= 20 ? "text-gain" :
            stats.probabilityOfLoss <= 40 ? "text-warning" : "text-loss"
          )}>
            {stats.probabilityOfLoss.toFixed(1)}%
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Value at Risk (95%)</div>
          <div className="text-lg font-bold text-loss">
            {stats.valueAtRisk95.toFixed(2)}%
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Expected Shortfall</div>
          <div className="text-lg font-bold text-loss">
            {stats.expectedShortfall.toFixed(2)}%
          </div>
        </Card>
      </div>

      {/* Distribution Statistics */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Mean Return</div>
          <div className="text-sm font-bold text-text">
            {stats.meanReturn >= 0 ? "+" : ""}{stats.meanReturn.toFixed(2)}%
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Std Deviation</div>
          <div className="text-sm font-bold text-text">{stats.stdDev.toFixed(2)}%</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Skewness</div>
          <div className="text-sm font-bold text-text">{stats.skewness.toFixed(2)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-text-muted mb-2">Kurtosis</div>
          <div className="text-sm font-bold text-text">{stats.kurtosis.toFixed(2)}</div>
        </Card>
      </div>

      {/* Comparison with Original */}
      <div className="rounded-lg border border-border bg-surface/40 p-4">
        <p className="text-sm text-text-muted">
          Based on {stats.numSimulations.toLocaleString()} simulations of resampled trades.
          Original backtest return: <span className={cn(
            "font-medium",
            stats.originalReturn >= 0 ? "text-gain" : "text-loss"
          )}>
            {stats.originalReturn >= 0 ? "+" : ""}{stats.originalReturn.toFixed(2)}%
          </span>
        </p>
      </div>
    </div>
  );
}
