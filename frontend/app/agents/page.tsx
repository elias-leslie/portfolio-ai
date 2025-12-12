"use client";

/**
 * Agent Telemetry Dashboard
 *
 * Displays AI agent execution metrics:
 * - Token usage by provider
 * - Run counts and success rates
 * - Daily telemetry charts
 * - Run history table
 */

import { useState } from "react";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Badge } from "@/components/ui/badge";
import {
  useTelemetrySummary,
  useRunHistory,
} from "@/lib/hooks/useAgentTelemetry";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { Activity, Cpu, Clock, CheckCircle2, XCircle } from "lucide-react";

import { PageContainer } from "@/components/shared/PageContainer";
import { ReviewQueue } from "@/components/agents/ReviewQueue";

export default function AgentsPage() {
  const [days, setDays] = useState(7);
  const { data: summary, isLoading: summaryLoading } = useTelemetrySummary(days);
  const { data: historyData, isLoading: historyLoading } = useRunHistory({
    limit: 20,
  });

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        title="Agent Telemetry"
        description="Monitor AI agent execution metrics, token usage, and performance"
      />

      {/* Period selector */}
      <div className="flex gap-2">
        {[7, 14, 30].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1 rounded-md text-sm ${days === d
                ? "bg-primary text-primary-foreground"
                : "bg-muted hover:bg-muted/80"
              }`}
          >
            {d} days
          </button>
        ))}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Runs"
          value={summary?.total_runs ?? 0}
          icon={<Activity className="h-4 w-4" />}
          loading={summaryLoading}
        />
        <MetricCard
          title="Success Rate"
          value={`${summary?.success_rate?.toFixed(1) ?? 0}%`}
          icon={<CheckCircle2 className="h-4 w-4" />}
          loading={summaryLoading}
          valueColor={
            (summary?.success_rate ?? 0) >= 90
              ? "text-green-500"
              : (summary?.success_rate ?? 0) >= 70
                ? "text-yellow-500"
                : "text-red-500"
          }
        />
        <MetricCard
          title="Total Tokens"
          value={formatNumber(summary?.total_tokens ?? 0)}
          icon={<Cpu className="h-4 w-4" />}
          loading={summaryLoading}
        />
        <MetricCard
          title="Avg Duration"
          value={`${formatDuration(summary?.avg_duration_ms ?? 0)}`}
          icon={<Clock className="h-4 w-4" />}
          loading={summaryLoading}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Runs Chart */}
        <SectionCard title="Daily Runs" contentClassName="h-64">
          {summaryLoading ? (
            <div className="h-full w-full animate-pulse bg-muted rounded" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[...(summary?.daily_data ?? [])].reverse()}
                margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(v) => v.slice(5)} // MM-DD
                />
                <YAxis />
                <Tooltip />
                <Bar
                  dataKey="total_runs"
                  fill="var(--color-chart-1)"
                  name="Runs"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </SectionCard>

        {/* Token Usage Chart */}
        <SectionCard title="Token Usage" contentClassName="h-64">
          {summaryLoading ? (
            <div className="h-full w-full animate-pulse bg-muted rounded" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={[...(summary?.daily_data ?? [])].reverse()}
                margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(v) => v.slice(5)} // MM-DD
                />
                <YAxis />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="total_tokens"
                  stroke="var(--color-chart-2)"
                  name="Tokens"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </SectionCard>
      </div>

      {/* Provider Metrics */}
      <SectionCard title="Provider Metrics">
        {summaryLoading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 w-full animate-pulse bg-muted rounded" />
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {summary?.by_provider.map((provider) => (
              <div
                key={provider.provider}
                className="flex items-center justify-between p-4 bg-muted/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="capitalize">
                    {provider.provider}
                  </Badge>
                  <span className="text-sm text-muted-foreground">
                    {provider.total_runs} runs
                  </span>
                </div>
                <div className="flex items-center gap-6 text-sm">
                  <div>
                    <span className="text-muted-foreground">Success: </span>
                    <span
                      className={
                        provider.success_rate >= 90
                          ? "text-green-500"
                          : provider.success_rate >= 70
                            ? "text-yellow-500"
                            : "text-red-500"
                      }
                    >
                      {provider.success_rate.toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Tokens: </span>
                    {formatNumber(provider.total_tokens)}
                  </div>
                  <div>
                    <span className="text-muted-foreground">Avg: </span>
                    {formatDuration(provider.avg_duration_ms)}
                  </div>
                </div>
              </div>
            ))}
            {summary?.by_provider.length === 0 && (
              <p className="text-muted-foreground text-center py-4">
                No provider data available
              </p>
            )}
          </div>
        )}
      </SectionCard>

      {/* Cross-Validation Review Queue */}
      <SectionCard title="Cross-Validation Review Queue">
        <ReviewQueue />
      </SectionCard>

      {/* Recent Runs */}
      <SectionCard title="Recent Runs">
        {historyLoading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 w-full animate-pulse bg-muted rounded" />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">Agent</th>
                  <th className="text-left p-2">Provider</th>
                  <th className="text-left p-2">Status</th>
                  <th className="text-left p-2">Duration</th>
                  <th className="text-left p-2">Tokens</th>
                  <th className="text-left p-2">Started</th>
                </tr>
              </thead>
              <tbody>
                {historyData?.runs.map((run) => (
                  <tr key={run.id} className="border-b hover:bg-muted/50">
                    <td className="p-2">
                      <Badge variant="secondary">{run.agent_type}</Badge>
                    </td>
                    <td className="p-2 capitalize">
                      {run.provider ?? "unknown"}
                    </td>
                    <td className="p-2">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="p-2">
                      {run.duration_ms ? formatDuration(run.duration_ms) : "-"}
                    </td>
                    <td className="p-2">
                      {run.token_usage?.total_tokens
                        ? formatNumber(run.token_usage.total_tokens)
                        : "-"}
                    </td>
                    <td className="p-2 text-muted-foreground">
                      {formatDate(run.started_at)}
                    </td>
                  </tr>
                ))}
                {historyData?.runs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-muted-foreground">
                      No runs found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </PageContainer>
  );
}

// Helper components
function MetricCard({
  title,
  value,
  icon,
  loading,
  valueColor,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  loading: boolean;
  valueColor?: string;
}) {
  return (
    <div className="p-4 bg-card border rounded-lg">
      <div className="flex items-center gap-2 text-muted-foreground mb-2">
        {icon}
        <span className="text-sm">{title}</span>
      </div>
      {loading ? (
        <div className="h-8 w-20 animate-pulse bg-muted rounded" />
      ) : (
        <span className={`text-2xl font-semibold ${valueColor ?? ""}`}>
          {value}
        </span>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "completed"
      ? "default"
      : status === "failed"
        ? "destructive"
        : "secondary";
  const icon =
    status === "completed" ? (
      <CheckCircle2 className="h-3 w-3" />
    ) : status === "failed" ? (
      <XCircle className="h-3 w-3" />
    ) : null;

  return (
    <Badge variant={variant} className="gap-1">
      {icon}
      {status}
    </Badge>
  );
}

// Helper functions
function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
}

function formatDuration(ms: number): string {
  if (ms >= 60000) return `${(ms / 60000).toFixed(1)}m`;
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

function formatDate(isoString: string): string {
  if (!isoString) return "-";
  const date = new Date(isoString);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
