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
// GapsOverview removed - trading requirements now in Features tab as "Data - *" categories
// CapabilitiesDashboard removed - Vision tab replaces it
import { ApiSourcesOverview } from "@/components/capabilities/ApiSourcesOverview";
// FeaturesTab removed - use SummitFlow at https://192.168.8.233:444/projects/portfolio-ai?tab=features
// VisionGoalsTab removed - use SummitFlow at https://192.168.8.233:444/projects/portfolio-ai?tab=vision
// LogTab removed - Beads handles session tracking
import { RulesViewer } from "@/components/rules/RulesViewer";
import { WorkflowCanvas } from "@/components/workflows/WorkflowCanvas";
// QATab removed - issues disconnected from workflow
// FilesTab removed - use SummitFlow for file browsing
// SitemapTab removed - use SummitFlow at https://192.168.8.233:444/projects/portfolio-ai?tab=sitemap
import {
  RefreshCw,
  Search,
  Filter,
  Database,
  Zap,
  Loader2,
  X,
  Cloud,
  BookOpen,
  GitBranch,
  ExternalLink,
} from "lucide-react";
import {
  fetchCapabilities,
  triggerScan,
  type CapabilityType,
} from "@/lib/api/capabilities";
// fetchGapSummary removed - trading requirements now in Features tab
import { toast } from "sonner";
import { PageContainer } from "@/components/shared/PageContainer";

type TabValue = "workflows" | "database" | "celery" | "sources" | "rules";

function CapabilitiesPageContent() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Get initial values from URL
  const initialHealthFilter = searchParams.get("health") || "all";
  const initialTab = (searchParams.get("tab") as TabValue) || "workflows";

  // Tab state
  const [activeTab, setActiveTab] = useState<TabValue>(initialTab);

  // Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [healthFilter, setHealthFilter] = useState<string>(initialHealthFilter);

  // Pagination
  const [page, setPage] = useState(0);
  const pageSize = 50;

  // Fetch health summary for tab counts (always enabled)
  interface HealthSummary {
    total: number;
    byType: {
      database: { active: number; orphaned: number; legacy: number; suspect: number };
      celery: { active: number; orphaned: number; legacy: number; suspect: number };
      api: { active: number; orphaned: number; legacy: number; suspect: number };
    };
    byStatus: { active: number; orphaned: number; legacy: number; suspect: number };
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
    enabled: activeTab !== "workflows" && activeTab !== "sources" && activeTab !== "rules",
  });

  // Trigger scan mutation
  const scanMutation = useMutation({
    mutationFn: triggerScan,
    onSuccess: (data) => {
      toast.success(data.message);
      // Refresh data after a delay (scan runs async)
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["capabilities"] });
      }, 2000);
    },
    onError: (error: Error) => {
      toast.error(`Failed to trigger scan: ${error.message}`);
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
          cap.capabilityType === "db"
            ? (cap.tableName || "")
            : cap.capabilityType === "celery"
              ? (cap.taskName || "")
              : (cap.endpointPath || "");
        return (
          name.toLowerCase().includes(query) ||
          cap.category?.toLowerCase().includes(query) ||
          cap.description?.toLowerCase().includes(query)
        );
      });
    }

    // Apply health filter
    if (healthFilter !== "all") {
      filtered = filtered.filter((cap) => cap.healthStatus === healthFilter);
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
      const priorityA = healthPriority[a.healthStatus] ?? 4;
      const priorityB = healthPriority[b.healthStatus] ?? 4;

      if (priorityA !== priorityB) {
        return priorityA - priorityB;
      }

      // Secondary sort by name for same health status
      const nameA =
        a.capabilityType === "db"
          ? (a.tableName || "")
          : a.capabilityType === "celery"
            ? (a.taskName || "")
            : (a.endpointPath || "");
      const nameB =
        b.capabilityType === "db"
          ? (b.tableName || "")
          : b.capabilityType === "celery"
            ? (b.taskName || "")
            : (b.endpointPath || "");
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
    const active = capabilitiesData.capabilities.filter((c) => c.healthStatus === "active").length;
    const orphaned = capabilitiesData.capabilities.filter((c) => c.healthStatus === "orphaned").length;
    const legacy = capabilitiesData.capabilities.filter((c) => c.healthStatus === "legacy").length;
    const suspect = capabilitiesData.capabilities.filter((c) => c.healthStatus === "suspect").length;
    const filtered = filteredCapabilities.length;

    return { total, active, orphaned, legacy, suspect, filtered };
  }, [capabilitiesData, filteredCapabilities]);

  // Render loading state
  if (capabilitiesLoading && !capabilitiesData) {
    return (
      <PageContainer className="space-y-6 py-4">
        <PageHeader
          title="System Capabilities"
          description="Loading capability registry..."
          size="md"
        />
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </PageContainer>
    );
  }

  // Count capabilities by type from health summary (always available)
  const dbStats = healthSummary?.byType?.database;
  const celeryStats = healthSummary?.byType?.celery;

  const dbCount = dbStats
    ? dbStats.active + dbStats.orphaned + dbStats.legacy + dbStats.suspect
    : 0;
  const celeryCount = celeryStats
    ? celeryStats.active + celeryStats.orphaned + celeryStats.legacy + celeryStats.suspect
    : 0;

  return (
    <PageContainer className="space-y-6 py-4">
      {/* Header */}
      <PageHeader
        title="System Registry"
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

      {/* SummitFlow link for dev tooling */}
      <div className="mb-4 flex items-center gap-2 rounded-lg border border-phosphor/30 bg-phosphor/5 px-4 py-2 text-sm">
        <ExternalLink className="h-4 w-4 text-phosphor" />
        <span className="text-muted-foreground">Dev tooling (Features, Vision, Sitemap, Files, Evidence) moved to</span>
        <a
          href="https://192.168.8.233:444/projects/portfolio-ai"
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-phosphor hover:underline"
        >
          SummitFlow
        </a>
      </div>

      {/* Tabs - domain-specific only: Workflows, Sources, Rules, DB, Tasks */}
      <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as TabValue)}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="workflows">
            <GitBranch className="mr-2 h-4 w-4" />
            Workflows
          </TabsTrigger>
          <TabsTrigger value="sources">
            <Cloud className="mr-2 h-4 w-4" />
            Sources
          </TabsTrigger>
          <TabsTrigger value="rules">
            <BookOpen className="mr-2 h-4 w-4" />
            Rules
          </TabsTrigger>
          <TabsTrigger value="database">
            <Database className="mr-2 h-4 w-4" />
            DB
            <span className="ml-1 rounded-full bg-surface-muted px-1.5 py-0.5 text-xs">
              {dbCount}
            </span>
          </TabsTrigger>
          <TabsTrigger value="celery">
            <Zap className="mr-2 h-4 w-4" />
            Tasks
            <span className="ml-1 rounded-full bg-surface-muted px-1.5 py-0.5 text-xs">
              {celeryCount}
            </span>
          </TabsTrigger>
        </TabsList>

        {/* Filters (for capability tabs only) */}
        {activeTab !== "workflows" && activeTab !== "sources" && activeTab !== "rules" && (
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

        {/* Workflows Tab */}
        <TabsContent value="workflows" className="mt-0">
          <div className="h-[calc(100vh-240px)] min-h-[400px]">
            <WorkflowCanvas fullHeight />
          </div>
        </TabsContent>

        {/* Database Tab */}
        <TabsContent value="database">
          <CapabilitiesTable capabilities={filteredCapabilities} />
        </TabsContent>

        {/* Celery Tasks Tab */}
        <TabsContent value="celery">
          <CapabilitiesTable capabilities={filteredCapabilities} />
        </TabsContent>

        {/* Tech Debt Tab removed - migrated to [DEBT] subtasks on features */}
        {/* Sitemap Tab removed - use SummitFlow */}

        {/* Data Sources Tab (formerly Sources) */}
        <TabsContent value="sources">
          <ApiSourcesOverview />
        </TabsContent>

        {/* Trading Rules Tab (formerly Rules) */}
        <TabsContent value="rules">
          <RulesViewer />
        </TabsContent>

        {/* Files Tab removed - use SummitFlow for file browsing */}
        {/* Features Tab removed - use SummitFlow */}
        {/* Vision Goals Tab removed - use SummitFlow */}

      </Tabs>

      {/* Pagination */}
      {activeTab !== "workflows" &&
        activeTab !== "sources" &&
        activeTab !== "rules" &&
        capabilitiesData &&
        capabilitiesData.total > pageSize && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {page * pageSize + 1} -{" "}
              {Math.min((page + 1) * pageSize, capabilitiesData?.total || 0)}{" "}
              of {capabilitiesData?.total || 0}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setPage(page - 1)} disabled={page === 0}>
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page + 1)}
                disabled={!capabilitiesData || (page + 1) * pageSize >= capabilitiesData.total}
              >
                Next
              </Button>
            </div>
          </div>
        )}
    </PageContainer>
  );
}

export default function CapabilitiesPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-bg">
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
