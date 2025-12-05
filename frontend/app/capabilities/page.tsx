/**
 * System Capabilities Registry - Main Page
 */

"use client";

import { useState, useMemo, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { CapabilitiesTable } from "@/components/capabilities/CapabilitiesTable";
import { InsightCard } from "@/components/capabilities/InsightCard";
import { CapabilitiesDashboard } from "@/components/capabilities/CapabilitiesDashboard";
import { GapsOverview } from "@/components/capabilities/GapsOverview";
import { ApiSourcesOverview } from "@/components/capabilities/ApiSourcesOverview";
import { RulesViewer } from "@/components/rules/RulesViewer";
import {
  RefreshCw,
  Search,
  Filter,
  Database,
  Zap,
  Globe,
  AlertTriangle,
  TrendingUp,
  Loader2,
  X,
  Cloud,
  BookOpen,
} from "lucide-react";
import {
  fetchCapabilities,
  fetchInsights,
  reviewInsight,
  triggerScan,
  type CapabilityType,
  type InsightSeverity,
  type InsightStatus,
} from "@/lib/api/capabilities";
import { fetchGapSummary } from "@/lib/api/gaps";
import { toast } from "sonner";

type TabValue = "dashboard" | "database" | "celery" | "api" | "insights" | "gaps" | "sources" | "rules";

function CapabilitiesPageContent() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Get initial health filter from URL
  const initialHealthFilter = searchParams.get("health") || "all";

  // Tab state
  const [activeTab, setActiveTab] = useState<TabValue>("dashboard");

  // Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [healthFilter, setHealthFilter] = useState<string>(initialHealthFilter);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [insightStatusFilter, setInsightStatusFilter] = useState<InsightStatus | "all">("all");

  // Pagination
  const [page, setPage] = useState(0);
  const pageSize = 50;

  // Fetch health summary for tab counts (always enabled)
  interface HealthSummary {
    total: number;
    by_type: {
      database: { active: number; orphaned: number; legacy: number; suspect: number };
      celery: { active: number; orphaned: number; legacy: number; suspect: number };
      api: { active: number; orphaned: number; legacy: number; suspect: number };
    };
    by_status: { active: number; orphaned: number; legacy: number; suspect: number };
  }

  const { data: healthSummary } = useQuery<HealthSummary>({
    queryKey: ["capabilities", "health-summary"],
    queryFn: async () => {
      const response = await fetch("/api/capabilities/health/summary");
      if (!response.ok) throw new Error("Failed to fetch health summary");
      return response.json();
    },
  });

  // Handle health filter change with URL sync
  const handleHealthFilterChange = (value: string) => {
    setHealthFilter(value);
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (value === "all") {
        params.delete("health");
      } else {
        params.set("health", value);
      }
      const newUrl = params.toString() ? `?${params.toString()}` : window.location.pathname;
      router.push(newUrl);
    }
  };

  // Determine capability type filter based on active tab
  const capabilityTypeFilter: "all" | CapabilityType =
    activeTab === "database"
      ? "db"
      : activeTab === "celery"
      ? "celery"
      : activeTab === "api"
      ? "api"
      : "all";

  // Fetch capabilities
  const {
    data: capabilitiesData,
    isLoading: capabilitiesLoading,
  } = useQuery({
    queryKey: [
      "capabilities",
      capabilityTypeFilter,
      categoryFilter,
      statusFilter,
      healthFilter,
      page,
      pageSize,
    ],
    queryFn: () =>
      fetchCapabilities({
        type: capabilityTypeFilter,
        category: categoryFilter !== "all" ? categoryFilter : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        limit: pageSize,
        offset: page * pageSize,
      }),
    enabled: activeTab !== "dashboard" && activeTab !== "insights" && activeTab !== "gaps" && activeTab !== "sources" && activeTab !== "rules",
  });

  // Fetch insights count (always enabled for tab badge)
  const { data: insightsCountData } = useQuery({
    queryKey: ["insights-count"],
    queryFn: () => fetchInsights({ limit: 1 }),
  });

  // Fetch insights for insights tab (full data when tab active)
  const {
    data: insightsData,
    isLoading: insightsLoading,
  } = useQuery({
    queryKey: ["insights", severityFilter, insightStatusFilter, page, pageSize],
    queryFn: () =>
      fetchInsights({
        severity: severityFilter !== "all" ? (severityFilter as InsightSeverity) : undefined,
        status: insightStatusFilter !== "all" ? insightStatusFilter : undefined,
        limit: pageSize,
        offset: page * pageSize,
      }),
    enabled: activeTab === "insights",
  });

  // Fetch gaps (trading intelligence gaps) - always fetch for tab badge count
  const {
    data: gapsData,
    isLoading: gapsLoading,
  } = useQuery({
    queryKey: ["gaps-summary"],
    queryFn: fetchGapSummary,
    staleTime: 60000, // Cache for 1 minute
  });

  // Trigger scan mutation
  const scanMutation = useMutation({
    mutationFn: triggerScan,
    onSuccess: (data) => {
      toast.success(data.message);
      // Refresh data after a delay (scan runs async)
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["capabilities"] });
        queryClient.invalidateQueries({ queryKey: ["insights"] });
      }, 2000);
    },
    onError: (error: Error) => {
      toast.error(`Failed to trigger scan: ${error.message}`);
    },
  });

  // Review insight mutation
  const reviewMutation = useMutation({
    mutationFn: ({
      insightId,
      status,
      reason,
    }: {
      insightId: number;
      status: InsightStatus;
      reason: string;
    }) => reviewInsight(insightId, { status, status_reason: reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["insights"] });
      queryClient.invalidateQueries({ queryKey: ["gaps"] });
      toast.success("Insight updated successfully");
    },
    onError: (error: Error) => {
      toast.error(`Failed to update insight: ${error.message}`);
    },
  });

  // Filter capabilities by search query and health status
  const filteredCapabilities = useMemo(() => {
    if (!capabilitiesData?.capabilities) return [];

    let filtered = capabilitiesData.capabilities;

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter((cap) => {
        const name =
          cap.capability_type === "db"
            ? (cap.table_name || "")
            : cap.capability_type === "celery"
            ? (cap.task_name || "")
            : (cap.endpoint_path || "");
        return (
          name.toLowerCase().includes(query) ||
          cap.category?.toLowerCase().includes(query) ||
          cap.description?.toLowerCase().includes(query)
        );
      });
    }

    // Apply health filter
    if (healthFilter !== "all") {
      filtered = filtered.filter((cap) => cap.health_status === healthFilter);
    }

    // Sort by health status (priority: orphaned > legacy > suspect > active)
    const healthPriority: Record<string, number> = {
      orphaned: 0,
      legacy: 1,
      suspect: 2,
      active: 3,
    };

    // Create a copy before sorting to avoid mutating the original array
    const sorted = [...filtered].sort((a, b) => {
      const priorityA = healthPriority[a.health_status] ?? 4;
      const priorityB = healthPriority[b.health_status] ?? 4;

      if (priorityA !== priorityB) {
        return priorityA - priorityB;
      }

      // Secondary sort by name for same health status
      const nameA =
        a.capability_type === "db"
          ? (a.table_name || "")
          : a.capability_type === "celery"
          ? (a.task_name || "")
          : (a.endpoint_path || "");
      const nameB =
        b.capability_type === "db"
          ? (b.table_name || "")
          : b.capability_type === "celery"
          ? (b.task_name || "")
          : (b.endpoint_path || "");
      return nameA.localeCompare(nameB);
    });

    return sorted;
  }, [capabilitiesData, searchQuery, healthFilter]);

  // Get unique categories from capabilities
  const categories = useMemo(() => {
    if (!capabilitiesData?.capabilities) return [];
    const cats = new Set(
      capabilitiesData.capabilities.map((c) => c.category).filter((c) => c !== null)
    );
    return Array.from(cats).sort();
  }, [capabilitiesData]);

  // Calculate health status counts
  const healthCounts = useMemo(() => {
    if (!capabilitiesData?.capabilities) {
      return { total: 0, active: 0, orphaned: 0, legacy: 0, suspect: 0, filtered: 0 };
    }

    const total = capabilitiesData.capabilities.length;
    const active = capabilitiesData.capabilities.filter((c) => c.health_status === "active").length;
    const orphaned = capabilitiesData.capabilities.filter((c) => c.health_status === "orphaned").length;
    const legacy = capabilitiesData.capabilities.filter((c) => c.health_status === "legacy").length;
    const suspect = capabilitiesData.capabilities.filter((c) => c.health_status === "suspect").length;
    const filtered = filteredCapabilities.length;

    return { total, active, orphaned, legacy, suspect, filtered };
  }, [capabilitiesData, filteredCapabilities]);

  // Render loading state
  if (capabilitiesLoading && !capabilitiesData) {
    return (
      <div className="bg-bg min-h-screen">
        <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
          <PageHeader
            title="System Capabilities"
            description="Loading capability registry..."
            size="md"
          />
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </div>
      </div>
    );
  }

  // Count capabilities by type from health summary (always available)
  const dbStats = healthSummary?.by_type?.database;
  const celeryStats = healthSummary?.by_type?.celery;
  const apiStats = healthSummary?.by_type?.api;

  const dbCount = dbStats
    ? dbStats.active + dbStats.orphaned + dbStats.legacy + dbStats.suspect
    : 0;
  const celeryCount = celeryStats
    ? celeryStats.active + celeryStats.orphaned + celeryStats.legacy + celeryStats.suspect
    : 0;
  const apiCount = apiStats
    ? apiStats.active + apiStats.orphaned + apiStats.legacy + apiStats.suspect
    : 0;

  return (
    <div className="bg-bg min-h-screen">
      <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <PageHeader
          title="System Capabilities Registry"
          description="Comprehensive view of database tables, background tasks, and API endpoints"
          size="md"
          actions={
            <Button onClick={() => scanMutation.mutate()} disabled={scanMutation.isPending}>
              {scanMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Scan System
            </Button>
          }
        />

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as TabValue)}>
          <TabsList className="grid w-full grid-cols-8">
            <TabsTrigger value="dashboard">
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="database">
              <Database className="mr-2 h-4 w-4" />
              Database
              <span className="ml-2 rounded-full bg-surface-muted px-2 py-0.5 text-xs">
                {dbCount}
              </span>
            </TabsTrigger>
            <TabsTrigger value="celery">
              <Zap className="mr-2 h-4 w-4" />
              Tasks
              <span className="ml-2 rounded-full bg-surface-muted px-2 py-0.5 text-xs">
                {celeryCount}
              </span>
            </TabsTrigger>
            <TabsTrigger value="api">
              <Globe className="mr-2 h-4 w-4" />
              Endpoints
              <span className="ml-2 rounded-full bg-surface-muted px-2 py-0.5 text-xs">
                {apiCount}
              </span>
            </TabsTrigger>
            <TabsTrigger value="insights">
              <AlertTriangle className="mr-2 h-4 w-4" />
              Insights
              {(insightsCountData?.pending_count ?? insightsData?.pending_count ?? 0) > 0 && (
                <span className="ml-2 rounded-full bg-accent/20 px-2 py-0.5 text-xs">
                  {insightsCountData?.pending_count ?? insightsData?.pending_count}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="gaps">
              <TrendingUp className="mr-2 h-4 w-4" />
              Gaps
              {gapsData && gapsData.total_gaps > 0 && (
                <span className="ml-2 rounded-full bg-accent/20 px-2 py-0.5 text-xs">
                  {gapsData.total_gaps}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="sources">
              <Cloud className="mr-2 h-4 w-4" />
              Sources
            </TabsTrigger>
            <TabsTrigger value="rules">
              <BookOpen className="mr-2 h-4 w-4" />
              Rules
            </TabsTrigger>
          </TabsList>

          {/* Filters (for capability tabs) */}
          {activeTab !== "dashboard" && activeTab !== "insights" && activeTab !== "gaps" && activeTab !== "sources" && activeTab !== "rules" && (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-3">
                {/* Search */}
                <div className="relative flex-1 min-w-[250px]">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type="text"
                    placeholder="Search capabilities..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>

                {/* Category Filter */}
                {categories.length > 0 && (
                  <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                    <SelectTrigger className="w-[180px]">
                      <Filter className="mr-2 h-4 w-4" />
                      <SelectValue placeholder="Category" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Categories</SelectItem>
                      {categories.map((cat) => (
                        <SelectItem key={cat} value={cat}>
                          {cat}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}

                {/* Status Filter (DB only) */}
                {activeTab === "database" && (
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[160px]">
                      <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Statuses</SelectItem>
                      <SelectItem value="fresh">Fresh</SelectItem>
                      <SelectItem value="stale">Stale</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                      <SelectItem value="unknown">Unknown</SelectItem>
                    </SelectContent>
                  </Select>
                )}

                {/* Health Filter */}
                <Select value={healthFilter} onValueChange={handleHealthFilterChange}>
                  <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="Health Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All ({healthCounts.total})</SelectItem>
                    <SelectItem value="active">Active ({healthCounts.active})</SelectItem>
                    <SelectItem value="orphaned">Orphaned ({healthCounts.orphaned})</SelectItem>
                    <SelectItem value="legacy">Legacy ({healthCounts.legacy})</SelectItem>
                    <SelectItem value="suspect">Suspect ({healthCounts.suspect})</SelectItem>
                  </SelectContent>
                </Select>

                {/* Clear Health Filter Button */}
                {healthFilter !== "all" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleHealthFilterChange("all")}
                  >
                    <X className="mr-2 h-4 w-4" />
                    Clear Filter
                  </Button>
                )}
              </div>

              {/* Result Count */}
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>
                  Showing {healthCounts.filtered}{" "}
                  {healthFilter !== "all" && `${healthFilter} `}
                  {healthCounts.filtered === 1 ? "capability" : "capabilities"}
                  {healthFilter !== "all" && ` (of ${healthCounts.total} total)`}
                </span>
              </div>
            </div>
          )}

          {/* Filters (for insights tab) */}
          {activeTab === "insights" && (
            <div className="flex flex-wrap gap-3">
              {/* Severity Filter */}
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="Severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Severities</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                </SelectContent>
              </Select>

              {/* Status Filter */}
              <Select
                value={insightStatusFilter}
                onValueChange={(val) => setInsightStatusFilter(val as InsightStatus | "all")}
              >
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="confirmed">Confirmed</SelectItem>
                  <SelectItem value="in_progress">In Progress</SelectItem>
                  <SelectItem value="fixed">Fixed</SelectItem>
                  <SelectItem value="dismissed">Dismissed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Dashboard Tab */}
          <TabsContent value="dashboard">
            <CapabilitiesDashboard />
          </TabsContent>

          {/* Database Tab */}
          <TabsContent value="database">
            <CapabilitiesTable capabilities={filteredCapabilities} />
          </TabsContent>

          {/* Celery Tasks Tab */}
          <TabsContent value="celery">
            <CapabilitiesTable capabilities={filteredCapabilities} />
          </TabsContent>

          {/* API Endpoints Tab */}
          <TabsContent value="api">
            <CapabilitiesTable capabilities={filteredCapabilities} />
          </TabsContent>

          {/* Insights Tab */}
          <TabsContent value="insights">
            {insightsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : insightsData && insightsData.insights.length > 0 ? (
              <div className="space-y-3">
                {insightsData.insights.map((insight) => (
                  <InsightCard
                    key={insight.id}
                    insight={insight}
                    onReview={async (insightId, status, reason) => {
                      await reviewMutation.mutateAsync({ insightId, status, reason });
                    }}
                    isLoading={reviewMutation.isPending}
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-border bg-surface p-8 text-center">
                <AlertTriangle className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
                <p className="mt-4 text-sm text-muted-foreground">No insights found</p>
              </div>
            )}
          </TabsContent>

          {/* Gaps Tab */}
          <TabsContent value="gaps">
            {gapsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : gapsData ? (
              <GapsOverview data={gapsData} />
            ) : (
              <div className="rounded-lg border border-border bg-surface p-8 text-center">
                <TrendingUp className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
                <p className="mt-4 text-sm text-muted-foreground">No gap data available</p>
              </div>
            )}
          </TabsContent>

          {/* Sources Tab */}
          <TabsContent value="sources">
            <ApiSourcesOverview />
          </TabsContent>

          {/* Rules Tab */}
          <TabsContent value="rules">
            <RulesViewer />
          </TabsContent>
        </Tabs>

        {/* Pagination */}
        {((activeTab !== "dashboard" &&
          activeTab !== "insights" &&
          activeTab !== "gaps" &&
          activeTab !== "sources" &&
          activeTab !== "rules" &&
          capabilitiesData &&
          capabilitiesData.total > pageSize) ||
          (activeTab === "insights" && insightsData && insightsData.total > pageSize)) && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {page * pageSize + 1} -{" "}
              {Math.min(
                (page + 1) * pageSize,
                activeTab === "insights"
                  ? insightsData?.total || 0
                  : capabilitiesData?.total || 0
              )}{" "}
              of{" "}
              {activeTab === "insights"
                ? insightsData?.total || 0
                : capabilitiesData?.total || 0}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setPage(page - 1)} disabled={page === 0}>
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page + 1)}
                disabled={
                  (activeTab === "insights" &&
                    (!insightsData || (page + 1) * pageSize >= insightsData.total)) ||
                  ((activeTab === "database" || activeTab === "celery" || activeTab === "api") &&
                    (!capabilitiesData || (page + 1) * pageSize >= capabilitiesData.total))
                }
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function CapabilitiesPage() {
  return (
    <Suspense fallback={
      <div className="bg-bg min-h-screen">
        <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
          <PageHeader
            title="System Capabilities"
            description="Loading..."
            size="md"
          />
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </div>
      </div>
    }>
      <CapabilitiesPageContent />
    </Suspense>
  );
}
