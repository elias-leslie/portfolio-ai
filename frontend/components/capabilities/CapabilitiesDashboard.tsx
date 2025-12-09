/**
 * Dashboard tab for System Capabilities - Health summary and critical tech debt
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
// Badge, ChevronRight, TrendingUp removed - no longer used after insights migration
import {
  Loader2,
  Database,
  Zap,
  Globe,
  AlertTriangle,
  CheckSquare,
} from "lucide-react";
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

interface FeaturesSummary {
  total: number;
  passes_breakdown: {
    passing?: number;
    failing?: number;
    unreviewed?: number;
  };
  category_breakdown: Record<string, number>;
  health_breakdown: Record<string, number>;
}

// getSeverityVariant and getCapabilityName removed - no longer needed after insights migration

/**
 * CapabilitiesDashboard component
 */
export function CapabilitiesDashboard() {
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

  // Fetch features summary
  const { data: featuresSummary } = useQuery<FeaturesSummary>({
    queryKey: ["features-summary"],
    queryFn: async () => {
      const response = await fetch("/api/capabilities/features/summary");
      if (!response.ok) {
        throw new Error("Failed to fetch features summary");
      }
      return response.json();
    },
  });

  // Insights query removed - tech debt migrated to [DEBT] subtasks on features
  // View debt items in Features tab with category filter "Tech Debt"

  // Tech debt type display names and colors (kept for reference)
  const techDebtTypeConfig: Record<string, { label: string; color: string }> = {
    dead_code: { label: "Dead Code", color: "text-red-400" },
    orphaned_infra: { label: "Orphaned Infra", color: "text-orange-400" },
    complexity: { label: "Complexity", color: "text-yellow-400" },
    dry_violation: { label: "DRY Violations", color: "text-purple-400" },
    test_coverage: { label: "Test Coverage", color: "text-blue-400" },
    dependency_issue: { label: "Dependencies", color: "text-cyan-400" },
    security_concern: { label: "Security", color: "text-pink-400" },
    broken_dependency: { label: "Broken Deps", color: "text-red-400" },
    missing_data: { label: "Missing Data", color: "text-orange-400" },
    data_quality: { label: "Data Quality", color: "text-yellow-400" },
    missing_capability: { label: "Missing Capability", color: "text-blue-400" },
    performance: { label: "Performance", color: "text-green-400" },
    freshness: { label: "Freshness", color: "text-teal-400" },
  };

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
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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

        {/* Features Health Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CheckSquare className="h-5 w-5 text-accent" />
              <CardTitle>Features ({featuresSummary?.total || 0})</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-gain" />
                  Verified
                </span>
                <span className="font-medium">{featuresSummary?.passes_breakdown?.passing || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-loss" />
                  Failing
                </span>
                <span className="font-medium">{featuresSummary?.passes_breakdown?.failing || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-2 text-sm">
                  <span className="h-2 w-2 rounded-full bg-accent" />
                  Unreviewed
                </span>
                <span className="font-medium">{featuresSummary?.passes_breakdown?.unreviewed || 0}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tech Debt - now tracked as [DEBT] subtasks on features */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-accent" />
            <CardTitle>Tech Debt</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <CheckSquare className="mb-3 h-12 w-12 text-gain opacity-50" />
            <p className="text-sm font-medium text-text">Migrated to Features</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Tech debt is now tracked as [DEBT] subtasks on features.
              <br />
              View in the Features tab with category &quot;Tech Debt&quot;.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
