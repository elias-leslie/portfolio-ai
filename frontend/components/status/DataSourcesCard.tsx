"use client";

import type { ReactNode } from "react";
import { TrendingUp, CheckCircle2, AlertCircle, XCircle, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { HealthResponse } from "@/lib/api/status";
import { ExpandableCard } from "@/components/status/ExpandableCard";

interface DataSourcesCardProps {
  health: HealthResponse;
}

type SourceHealth = NonNullable<HealthResponse["sources"]>[string];

export function DataSourcesCard({ health }: DataSourcesCardProps) {
  const sources = health.sources ?? {};
  const sourceEntries = Object.entries(sources) as [string, SourceHealth][];
  const healthySources = sourceEntries.filter(([, s]) => s.status === "ok");
  const unhealthySources = sourceEntries.filter(([, s]) => s.status !== "ok");

  const statusCounts = sourceEntries.reduce(
    (acc, [, sourceHealth]) => {
      if (sourceHealth.status === "ok") acc.healthy += 1;
      else if (sourceHealth.status === "degraded") acc.degraded += 1;
      else if (sourceHealth.status === "down") acc.down += 1;
      else acc.unknown += 1;
      return acc;
    },
    { healthy: 0, degraded: 0, down: 0, unknown: 0 },
  );

  const summary = (() => {
    if (!sourceEntries.length) return "No data sources configured";
    const parts: string[] = [];
    if (statusCounts.healthy) parts.push(`${statusCounts.healthy} healthy`);
    if (statusCounts.degraded) parts.push(`${statusCounts.degraded} degraded`);
    if (statusCounts.down) parts.push(`${statusCounts.down} down`);
    if (statusCounts.unknown) parts.push(`${statusCounts.unknown} unknown`);
    return parts.join(" • ") || "Telemetry pending";
  })();

  return (
    <ExpandableCard
      title={
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          <span>Data Sources</span>
        </div>
      }
      description="Vendor uptime, latency, and cooldown telemetry."
      summary={summary}
      defaultCollapsed
    >
      {!sourceEntries.length ? (
        <p className="text-sm text-muted-foreground">
          No data sources configured. Add vendors in your configuration to begin ingesting market data.
        </p>
      ) : (
        <div className="space-y-6">
          <SourceGroup
            title="Sources Requiring Attention"
            tone="destructive"
            count={unhealthySources.length}
          >
            {unhealthySources
              .sort(([aName], [bName]) => aName.localeCompare(bName))
              .map(([sourceName, sourceHealth]) =>
                renderSourceRow(sourceName, sourceHealth),
              )}
          </SourceGroup>

          <SourceGroup title="Healthy Sources" tone="success" count={healthySources.length}>
            {healthySources
              .sort(([aName], [bName]) => aName.localeCompare(bName))
              .map(([sourceName, sourceHealth]) =>
                renderSourceRow(sourceName, sourceHealth),
              )}
          </SourceGroup>
        </div>
      )}
    </ExpandableCard>
  );
}

function SourceGroup({
  title,
  tone,
  count,
  children,
}: {
  title: string;
  tone: "destructive" | "success";
  count: number;
  children: ReactNode;
}) {
  if (!count) return null;

  const badge =
    tone === "destructive" ? (
      <Badge variant="destructive">{count}</Badge>
    ) : (
      <Badge className="bg-green-500 text-white">{count}</Badge>
    );

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold">
        {badge}
        <span>{title}</span>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function renderSourceRow(sourceName: string, sourceHealth: SourceHealth) {
  return (
    <div
      key={sourceName}
      className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/50"
    >
      <div className="flex flex-1 items-center gap-3">
        {getStatusIcon(sourceHealth.status)}
        <div className="flex-1">
          <div className="font-medium capitalize">{sourceName.replace(/_/g, " ")}</div>
          <div className="mt-1 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Last success: {formatTimestamp(sourceHealth.lastSuccess)}
            </div>
            {sourceHealth.successRate != null && (
              <div>Success rate: {sourceHealth.successRate.toFixed(1)}%</div>
            )}
            {sourceHealth.avgLatencyMs != null && (
              <div>Avg latency: {sourceHealth.avgLatencyMs}ms</div>
            )}
          </div>
          {sourceHealth.inCooldown && (
            <div className="mt-1 flex items-center gap-1 text-xs text-yellow-600">
              <AlertCircle className="h-3 w-3" />
              In cooldown ({sourceHealth.cooldownRemainingSeconds}s remaining)
            </div>
          )}
          {sourceHealth.rateLimitHits > 0 && (
            <div className="mt-1 text-xs text-orange-600">
              Rate limit hits: {sourceHealth.rateLimitHits}
            </div>
          )}
        </div>
      </div>
      <div>{getStatusBadge(sourceHealth.status)}</div>
    </div>
  );
}

function getStatusIcon(status: string) {
  switch (status) {
    case "ok":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "degraded":
      return <AlertCircle className="h-4 w-4 text-yellow-500" />;
    case "down":
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <AlertCircle className="h-4 w-4 text-gray-500" />;
  }
}

function getStatusBadge(status: string) {
  switch (status) {
    case "ok":
      return <Badge className="bg-green-500 text-white">Healthy</Badge>;
    case "degraded":
      return <Badge className="bg-yellow-500 text-white">Degraded</Badge>;
    case "down":
      return <Badge variant="destructive">Down</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function formatTimestamp(timestamp: string | null | undefined) {
  if (!timestamp) return "Never";
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  } catch {
    return "Unknown";
  }
}
