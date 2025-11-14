/**
 * System Capabilities Registry - Main Page
 */

"use client";

import { useState, useMemo } from "react";
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
import { CapabilityDetailModal } from "@/components/capabilities/CapabilityDetailModal";
import { InsightCard } from "@/components/capabilities/InsightCard";
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
} from "lucide-react";
import {
  fetchCapabilities,
  fetchInsights,
  reviewInsight,
  triggerScan,
  type Capability,
  type CapabilityType,
  type InsightSeverity,
  type InsightStatus,
} from "@/lib/api/capabilities";
import { toast } from "sonner";

type TabValue = "all" | "database" | "celery" | "api" | "insights" | "gaps";

export default function CapabilitiesPage() {
  const queryClient = useQueryClient();

  // Tab state
  const [activeTab, setActiveTab] = useState<TabValue>("all");

  // Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [insightStatusFilter, setInsightStatusFilter] = useState<InsightStatus | "all">("all");

  // Pagination
  const [page, setPage] = useState(0);
  const pageSize = 50;

  // Modal state
  const [selectedCapability, setSelectedCapability] = useState<Capability | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

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
    error: capabilitiesError,
  } = useQuery({
    queryKey: [
      "capabilities",
      capabilityTypeFilter,
      categoryFilter,
      statusFilter,
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
    enabled: activeTab !== "insights" && activeTab !== "gaps",
  });

  // Fetch insights for insights tab
  const {
    data: insightsData,
    isLoading: insightsLoading,
    error: insightsError,
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

  // Fetch gaps (missing capabilities)
  const {
    data: gapsData,
    isLoading: gapsLoading,
    error: gapsError,
  } = useQuery({
    queryKey: ["gaps", page, pageSize],
    queryFn: () =>
      fetchInsights({
        type: "missing_capability",
        status: "pending",
        limit: pageSize,
        offset: page * pageSize,
      }),
    enabled: activeTab === "gaps",
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

  // Filter capabilities by search query
  const filteredCapabilities = useMemo(() => {
    if (!capabilitiesData?.capabilities) return [];

    let filtered = capabilitiesData.capabilities;

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter((cap) => {
        const name =
          cap.capability_type === "db"
            ? cap.table_name
            : cap.capability_type === "celery"
            ? cap.task_name
            : cap.endpoint_path;
        return (
          name.toLowerCase().includes(query) ||
          cap.category?.toLowerCase().includes(query) ||
          cap.description?.toLowerCase().includes(query)
        );
      });
    }

    return filtered;
  }, [capabilitiesData, searchQuery]);

  // Get unique categories from capabilities
  const categories = useMemo(() => {
    if (!capabilitiesData?.capabilities) return [];
    const cats = new Set(
      capabilitiesData.capabilities.map((c) => c.category).filter((c) => c !== null)
    );
    return Array.from(cats).sort();
  }, [capabilitiesData]);

  // Handle capability row click
  const handleCapabilityClick = (capability: Capability) => {
    setSelectedCapability(capability);
    setIsModalOpen(true);
  };

  // Handle modal close
  const handleModalClose = () => {
    setIsModalOpen(false);
    setSelectedCapability(null);
  };

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

  // Count capabilities by type
  const dbCount =
    capabilitiesData?.capabilities.filter((c) => c.capability_type === "db").length || 0;
  const celeryCount =
    capabilitiesData?.capabilities.filter((c) => c.capability_type === "celery").length || 0;
  const apiCount =
    capabilitiesData?.capabilities.filter((c) => c.capability_type === "api").length || 0;

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
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="all">
              All
              <span className="ml-2 rounded-full bg-surface-muted px-2 py-0.5 text-xs">
                {capabilitiesData?.total || 0}
              </span>
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
              {insightsData && insightsData.total > 0 && (
                <span className="ml-2 rounded-full bg-accent/20 px-2 py-0.5 text-xs">
                  {insightsData.total}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="gaps">
              <TrendingUp className="mr-2 h-4 w-4" />
              Gaps
              {gapsData && gapsData.total > 0 && (
                <span className="ml-2 rounded-full bg-accent/20 px-2 py-0.5 text-xs">
                  {gapsData.total}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          {/* Filters (for capability tabs) */}
          {activeTab !== "insights" && activeTab !== "gaps" && (
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

          {/* All Capabilities Tab */}
          <TabsContent value="all">
            <CapabilitiesTable
              capabilities={filteredCapabilities}
              onRowClick={handleCapabilityClick}
            />
          </TabsContent>

          {/* Database Tab */}
          <TabsContent value="database">
            <CapabilitiesTable
              capabilities={filteredCapabilities}
              onRowClick={handleCapabilityClick}
            />
          </TabsContent>

          {/* Celery Tasks Tab */}
          <TabsContent value="celery">
            <CapabilitiesTable
              capabilities={filteredCapabilities}
              onRowClick={handleCapabilityClick}
            />
          </TabsContent>

          {/* API Endpoints Tab */}
          <TabsContent value="api">
            <CapabilitiesTable
              capabilities={filteredCapabilities}
              onRowClick={handleCapabilityClick}
            />
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
            ) : gapsData && gapsData.insights.length > 0 ? (
              <div className="space-y-3">
                <div className="rounded-lg border border-border bg-surface p-4">
                  <h3 className="text-lg font-medium mb-2">Missing Capabilities</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    The AI has identified {gapsData.total} potential data sources or features that
                    could enhance the system.
                  </p>
                </div>
                {gapsData.insights.map((insight) => (
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
                <TrendingUp className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
                <p className="mt-4 text-sm text-muted-foreground">No capability gaps identified</p>
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* Pagination */}
        {((activeTab !== "insights" &&
          activeTab !== "gaps" &&
          capabilitiesData &&
          capabilitiesData.total > pageSize) ||
          (activeTab === "insights" && insightsData && insightsData.total > pageSize) ||
          (activeTab === "gaps" && gapsData && gapsData.total > pageSize)) && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {page * pageSize + 1} -{" "}
              {Math.min(
                (page + 1) * pageSize,
                activeTab === "insights"
                  ? insightsData?.total || 0
                  : activeTab === "gaps"
                  ? gapsData?.total || 0
                  : capabilitiesData?.total || 0
              )}{" "}
              of{" "}
              {activeTab === "insights"
                ? insightsData?.total || 0
                : activeTab === "gaps"
                ? gapsData?.total || 0
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
                  (activeTab === "gaps" &&
                    (!gapsData || (page + 1) * pageSize >= gapsData.total)) ||
                  (activeTab !== "insights" &&
                    activeTab !== "gaps" &&
                    (!capabilitiesData || (page + 1) * pageSize >= capabilitiesData.total))
                }
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      <CapabilityDetailModal
        capability={selectedCapability}
        isOpen={isModalOpen}
        onClose={handleModalClose}
      />
    </div>
  );
}
