/**
 * Dashboard tab for System Capabilities - Health summary and recent insights
 */

"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ChevronRight,
  Loader2,
  Database,
  Zap,
  Globe,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import {
  fetchInsights,
  type CapabilityInsight,
  type InsightSeverity,
} from "@/lib/api/capabilities";
import { formatDistanceToNow } from "date-fns";

interface HealthSummary {
  total: number;
  by_type: {
    database: {
      active: number;
      orphaned: number;
      legacy: number;
      suspect: number;
    };
    celery: {
      active: number;
      orphaned: number;
      legacy: number;
      suspect: number;
    };
    api: {
      active: number;
      orphaned: number;
      legacy: number;
      suspect: number;
    };
  };
  by_status: {
    active: number;
    orphaned: number;
    legacy: number;
    suspect: number;
  };
  last_scan?: string;
  next_scan?: string;
}

/**
 * Get badge variant based on severity
 */
function getSeverityVariant(severity: InsightSeverity): "default" | "destructive" | "warning" {
  switch (severity) {
    case "critical":
      return "destructive";
    case "high":
    case "medium":
      return "warning";
    default:
      return "default";
  }
}

/**
 * Determine capability name from insight
 */
function getCapabilityName(insight: CapabilityInsight): string {
  if (insight.table_name) return insight.table_name;
  if (insight.task_name) return insight.task_name;
  if (insight.endpoint_path) return insight.endpoint_path;
  return "Unknown";
}

/**
 * CapabilitiesDashboard component
 */
export function CapabilitiesDashboard() {
  const router = useRouter();

  // Fetch health summary
  const { data: healthSummary, isLoading: healthLoading } = useQuery<HealthSummary>({
    queryKey: ["capabilities", "health-summary"],
    queryFn: async () => {
      const response = await fetch("/api/capabilities/health/summary");
      if (!response.ok) {
        throw new Error("Failed to fetch health summary");
      }
      return response.json();
    },
  });

  // Fetch recent critical/warning insights - ONLY PENDING (not fixed/dismissed)
  const { data: insightsData, isLoading: insightsLoading } = useQuery({
    queryKey: ["capability-insights", "dashboard", "pending"],
    queryFn: () =>
      fetchInsights({
        status: "pending",
        limit: 10,
        offset: 0,
      }),
  });

  // Navigate to capability detail from insight
  const navigateToInsight = (insight: CapabilityInsight) => {
    // Determine tab based on capability_type
    const tabMap: Record<string, string> = {
      db: "database",
      celery: "celery",
      api: "api",
    };

    const tab = tabMap[insight.capability_type] || "all";

    // Navigate with query params (expand will be handled by the target tab)
    if (insight.capability_id) {
      router.push(`/capabilities?tab=${tab}&expand=${insight.capability_id}`);
    } else {
      // If no capability_id (missing capability), go to gaps tab
      router.push(`/capabilities?tab=gaps`);
    }
  };

  // Filter insights to show only critical and high severity
  const criticalInsights =
    insightsData?.insights.filter(
      (i) => i.severity === "critical" || i.severity === "high"
    ) || [];

  if (healthLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const dbStats = healthSummary?.by_type?.database || {
    active: 0,
    suspect: 0,
    orphaned: 0,
    legacy: 0,
  };
  const celeryStats = healthSummary?.by_type?.celery || {
    active: 0,
    suspect: 0,
    orphaned: 0,
    legacy: 0,
  };
  const apiStats = healthSummary?.by_type?.api || {
    active: 0,
    suspect: 0,
    orphaned: 0,
    legacy: 0,
  };

  const dbTotal = dbStats.active + dbStats.suspect + dbStats.orphaned + dbStats.legacy;
  const celeryTotal =
    celeryStats.active + celeryStats.suspect + celeryStats.orphaned + celeryStats.legacy;
  const apiTotal = apiStats.active + apiStats.suspect + apiStats.orphaned + apiStats.legacy;

  return (
    <div className="space-y-6">
      {/* Scan Info Bar */}
      {(healthSummary?.last_scan || healthSummary?.next_scan) && (
        <div className="rounded-lg border border-border bg-surface p-4 text-sm text-muted-foreground">
          {healthSummary?.last_scan && (
            <span>
              Last scan: {formatDistanceToNow(new Date(healthSummary.last_scan), { addSuffix: true })}
            </span>
          )}
          {healthSummary?.next_scan && (
            <span className="ml-4">
              Next scan: {formatDistanceToNow(new Date(healthSummary.next_scan), { addSuffix: true })}
            </span>
          )}
        </div>
      )}

      {/* Health Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Database Health Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-accent" />
              <CardTitle>Database Tables ({dbTotal})</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-gain" />
                  Active
                </span>
                <span className="font-medium">{dbStats.active}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-accent" />
                  Suspect
                </span>
                <span className="font-medium">{dbStats.suspect}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-loss" />
                  Orphaned
                </span>
                <span className="font-medium">{dbStats.orphaned}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-muted-foreground" />
                  Legacy
                </span>
                <span className="font-medium">{dbStats.legacy}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Tasks Health Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-accent" />
              <CardTitle>Background Tasks ({celeryTotal})</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-gain" />
                  Active
                </span>
                <span className="font-medium">{celeryStats.active}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-accent" />
                  Suspect
                </span>
                <span className="font-medium">{celeryStats.suspect}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-loss" />
                  Orphaned
                </span>
                <span className="font-medium">{celeryStats.orphaned}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-muted-foreground" />
                  Legacy
                </span>
                <span className="font-medium">{celeryStats.legacy}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Endpoints Health Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-accent" />
              <CardTitle>API Endpoints ({apiTotal})</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-gain" />
                  Active
                </span>
                <span className="font-medium">{apiStats.active}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-accent" />
                  Suspect
                </span>
                <span className="font-medium">{apiStats.suspect}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-loss" />
                  Orphaned
                </span>
                <span className="font-medium">{apiStats.orphaned}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-muted-foreground" />
                  Legacy
                </span>
                <span className="font-medium">{apiStats.legacy}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Critical Insights */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-accent" />
              <CardTitle>Recent Critical & High Priority Insights</CardTitle>
            </div>
            {criticalInsights.length > 0 && (
              <Badge variant="warning">{criticalInsights.length}</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {insightsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : criticalInsights.length > 0 ? (
            <div className="space-y-2">
              {criticalInsights.map((insight) => (
                <div
                  key={insight.id}
                  className="flex cursor-pointer items-start gap-3 rounded-lg p-3 transition-colors hover:bg-surface-muted"
                  onClick={() => navigateToInsight(insight)}
                >
                  <Badge variant={getSeverityVariant(insight.severity)} className="mt-0.5">
                    {insight.severity.toUpperCase()}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="text-sm font-medium text-text">
                        {getCapabilityName(insight)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {insight.capability_type}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {insight.finding}
                    </p>
                  </div>
                  <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground mt-1" />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <TrendingUp className="mb-3 h-12 w-12 text-gain opacity-50" />
              <p className="text-sm font-medium text-text">All Clear!</p>
              <p className="mt-1 text-xs text-muted-foreground">
                No critical or high priority issues detected
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
