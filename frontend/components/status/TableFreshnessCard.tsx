"use client";

import { useState, useEffect } from "react";
import { Database, CheckCircle2, AlertCircle, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ExpandableCard } from "@/components/status/ExpandableCard";
import {
  fetchTableFreshness,
  TableFreshnessResponse,
  TableFreshnessStatus,
} from "@/lib/api/status";

export function TableFreshnessCard() {
  const [data, setData] = useState<TableFreshnessResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadFreshness = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetchTableFreshness();
        setData(response);
      } catch (err) {
        console.error("Failed to fetch table freshness:", err);
        setError("Failed to load table freshness data");
      } finally {
        setIsLoading(false);
      }
    };

    loadFreshness();
    const interval = setInterval(loadFreshness, 60000);
    return () => clearInterval(interval);
  }, []);

  const summaryText = (() => {
    if (error) return error;
    if (!data) return "Loading freshness telemetry...";
    return `${data.criticalCount} critical • ${data.staleCount} stale • ${data.freshCount} fresh`;
  })();

  if (!data || isLoading) {
    return (
      <ExpandableCard
        title={<HeaderTitle />}
        description="Fresh < interval • Stale < 2× interval • Critical > 2× interval"
        summary={summaryText}
        defaultCollapsed
      >
        <p className="text-sm text-muted-foreground">{summaryText}</p>
      </ExpandableCard>
    );
  }

  if (error) {
    return (
      <ExpandableCard
        title={<HeaderTitle />}
        description="Fresh < interval • Stale < 2× interval • Critical > 2× interval"
        summary={summaryText}
        defaultCollapsed={false}
      >
        <p className="text-sm text-destructive">{error}</p>
      </ExpandableCard>
    );
  }

  const freshTables = data.tables.filter((t) => t.status === "fresh");
  const staleTables = data.tables.filter((t) => t.status === "stale");
  const criticalTables = data.tables.filter((t) => t.status === "critical");
  const errorTables = data.tables.filter(
    (t) => t.status === "error" || t.status === "unknown"
  );

  return (
    <ExpandableCard
      title={<HeaderTitle />}
      description="Fresh < interval • Stale < 2× interval • Critical > 2× interval"
      summary={summaryText}
      defaultCollapsed
    >
      <div className="space-y-4">
        {renderSection("Critical Tables", criticalTables, "destructive", "> 2× refresh interval")}
        {renderSection("Stale Tables", staleTables, "warning", "< 2× refresh interval")}
        {renderSection("Fresh Tables", freshTables, "success", "< refresh interval")}
        {renderSection("Unknown/Error Tables", errorTables, "muted", "Telemetry missing or failed")}
      </div>
    </ExpandableCard>
  );
}

function HeaderTitle() {
  return (
    <div className="flex items-center gap-2">
      <Database className="h-5 w-5" />
      <span>Data Freshness</span>
    </div>
  );
}

function renderSection(
  title: string,
  rows: TableFreshnessStatus[],
  tone: "destructive" | "warning" | "success" | "muted",
  hint?: string,
) {
  if (!rows.length) return null;

  const badge =
    tone === "destructive"
      ? <Badge variant="destructive">{rows.length}</Badge>
      : tone === "warning"
        ? <Badge className="bg-status-warning text-text-inverted">{rows.length}</Badge>
        : tone === "success"
          ? <Badge className="bg-status-success text-text-inverted">{rows.length}</Badge>
          : <Badge variant="outline">{rows.length}</Badge>;

  return (
    <section className="space-y-2">
      <div className="font-semibold flex items-center gap-2 text-sm">
        {toneIcon(tone)}
        <span>{title}</span>
        {hint && (
          <span className="text-xs font-normal text-muted-foreground">({hint})</span>
        )}
        {badge}
      </div>
      <div className="space-y-2">
        {rows.map((table) => (
          <TableRow key={table.tableName} table={table} />
        ))}
      </div>
    </section>
  );
}

function toneIcon(tone: "destructive" | "warning" | "success" | "muted") {
  switch (tone) {
    case "destructive":
      return <XCircle className="h-4 w-4 text-status-error" />;
    case "warning":
      return <AlertCircle className="h-4 w-4 text-status-warning" />;
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-status-success" />;
    default:
      return <AlertCircle className="h-4 w-4 text-text-muted" />;
  }
}

function TableRow({ table }: { table: TableFreshnessStatus }) {
  const ageText = formatAge(table.ageHours);
  const refreshText = table.expectedRefreshHours
    ? `refreshes every ${table.expectedRefreshHours}h`
    : null;
  const rowsText =
    table.rowCount && table.rowCount > 0
      ? `${table.rowCount.toLocaleString()} rows`
      : null;

  return (
    <div className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors">
      <div className="flex-1">
        <div className="font-medium">{formatTableName(table.tableName)}</div>
        <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground mt-1">
          <div>{ageText}</div>
          {refreshText && <div>{refreshText}</div>}
          {rowsText && <div>{rowsText}</div>}
        </div>
      </div>
      {statusBadge(table.status)}
    </div>
  );
}

function statusBadge(status: string) {
  switch (status) {
    case "fresh":
      return <Badge className="bg-status-success text-text-inverted">Fresh</Badge>;
    case "stale":
      return <Badge className="bg-status-warning text-text-inverted">Stale</Badge>;
    case "critical":
      return <Badge variant="destructive">Critical</Badge>;
    case "error":
      return <Badge variant="outline">Error</Badge>;
    default:
      return <Badge variant="outline">Unknown</Badge>;
  }
}

function formatTableName(tableName: string) {
  return tableName
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatAge(ageHours: number | null) {
  if (ageHours === null) return "Unknown age";
  if (ageHours < 1) return `${Math.round(ageHours * 60)}m ago`;
  if (ageHours < 24) return `${Math.round(ageHours)}h ago`;
  const days = Math.round(ageHours / 24);
  return `${days}d ago`;
}
