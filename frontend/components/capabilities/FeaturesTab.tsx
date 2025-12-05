"use client";

import { useState, Fragment } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  FileText,
} from "lucide-react";

// Task interface for subtasks
interface Task {
  id: number | null;
  task_id: string;
  description: string;
  completed: boolean;
  order_num: number;
  completed_at: string | null;
  completed_by: string | null;
}

interface Feature {
  id: number | null;
  feature_id: string;
  name: string;
  category: string | null;
  description: string | null;
  passes: boolean | null;
  layers: string[];
  layer_results: Record<string, { passed: boolean; evidence?: string }>;
  test_count: number;
  task_file: string | null;
  task_section: string | null;
  task_file_exists: boolean;
  total_tasks: number;
  completed_tasks: number;
  completion_pct: number;
  health_status: string;
  needs_review: boolean;
  last_verified_at: string | null;
  verified_by: string | null;
  tasks: Task[];
}

interface FeaturesResponse {
  features: Feature[];
  total: number;
  filtered: number;
}

interface FeaturesSummary {
  total: number;
  passes_breakdown: Record<string, number>;
  category_breakdown: Record<string, number>;
  health_breakdown: Record<string, number>;
}

export function FeaturesTab() {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [passesFilter, setPassesFilter] = useState("all");
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [pageSize, setPageSize] = useState(25);
  const [currentPage, setCurrentPage] = useState(1);
  const queryClient = useQueryClient();

  // Toggle row expansion
  const toggleRow = (featureId: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(featureId)) {
        next.delete(featureId);
      } else {
        next.add(featureId);
      }
      return next;
    });
  };

  // Toggle task completion
  const toggleTask = async (featureId: string, taskId: string, completed: boolean) => {
    try {
      const response = await fetch(`/api/capabilities/features/${featureId}/tasks/${taskId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ completed, completed_by: "manual" }),
      });
      if (!response.ok) throw new Error("Failed to toggle task");
      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ["features"] });
    } catch {
      toast.error("Failed to toggle task completion");
    }
  };

  // Fetch features - first get total, then fetch all
  const { data: featuresData, isLoading } = useQuery<FeaturesResponse>({
    queryKey: ["features", categoryFilter, passesFilter],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (categoryFilter !== "all") params.set("category", categoryFilter);
      if (passesFilter !== "all") params.set("passes", passesFilter);

      // First request to get total count
      params.set("limit", "1");
      const countResponse = await fetch(`/api/capabilities/features/?${params}`);
      if (!countResponse.ok) throw new Error("Failed to fetch features");
      const countData = await countResponse.json();
      const total = countData.total || 200;

      // Fetch all features (up to 1000 max for safety)
      params.set("limit", String(Math.min(total, 1000)));
      const response = await fetch(`/api/capabilities/features/?${params}`);
      if (!response.ok) throw new Error("Failed to fetch features");
      return response.json();
    },
  });

  // Fetch summary for counts
  const { data: summaryData } = useQuery<FeaturesSummary>({
    queryKey: ["features-summary"],
    queryFn: async () => {
      const response = await fetch("/api/capabilities/features/summary");
      if (!response.ok) throw new Error("Failed to fetch summary");
      return response.json();
    },
  });

  // Filter features by search query
  const filteredFeatures = featuresData?.features.filter((f) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      f.feature_id.toLowerCase().includes(q) ||
      f.name.toLowerCase().includes(q) ||
      f.category?.toLowerCase().includes(q) ||
      f.description?.toLowerCase().includes(q)
    );
  }) ?? [];

  // Pagination calculations
  const totalFiltered = filteredFeatures.length;
  const totalPages = Math.ceil(totalFiltered / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalFiltered);
  const paginatedFeatures = filteredFeatures.slice(startIndex, endIndex);

  // Reset to page 1 when filters change
  const handlePageSizeChange = (newSize: string) => {
    setPageSize(Number(newSize));
    setCurrentPage(1);
  };

  // Reset to page 1 when search/filters change
  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setCurrentPage(1);
  };

  // Get unique categories
  const categories = summaryData?.category_breakdown
    ? Object.keys(summaryData.category_breakdown).sort()
    : [];

  // Category color mapping (deterministic colors per category)
  const categoryColors: Record<string, { bg: string; text: string; border: string }> = {
    "Dashboard": { bg: "#3b82f620", text: "#60a5fa", border: "#3b82f640" },
    "Watchlist": { bg: "#8b5cf620", text: "#a78bfa", border: "#8b5cf640" },
    "Portfolio": { bg: "#06b6d420", text: "#22d3ee", border: "#06b6d440" },
    "Trading": { bg: "#f59e0b20", text: "#fbbf24", border: "#f59e0b40" },
    "Backtest": { bg: "#ec489920", text: "#f472b6", border: "#ec489940" },
    "Strategies": { bg: "#10b98120", text: "#34d399", border: "#10b98140" },
    "Recs": { bg: "#6366f120", text: "#818cf8", border: "#6366f140" },
    "Agents": { bg: "#ef444420", text: "#f87171", border: "#ef444440" },
    "Status": { bg: "#14b8a620", text: "#2dd4bf", border: "#14b8a640" },
    "Settings": { bg: "#78716c20", text: "#a8a29e", border: "#78716c40" },
    "Capabilities": { bg: "#0ea5e920", text: "#38bdf8", border: "#0ea5e940" },
    "Infrastructure": { bg: "#64748b20", text: "#94a3b8", border: "#64748b40" },
  };
  const defaultCategoryColor = { bg: "#71717a20", text: "#a1a1aa", border: "#71717a40" };

  // Get row background color based on passes status
  const getRowBgColor = (passes: boolean | null) => {
    if (passes === true) return "rgba(34, 197, 94, 0.05)";  // green tint
    if (passes === false) return "rgba(239, 68, 68, 0.08)"; // red tint
    return "transparent";
  };

  // Render passes badge
  const renderPassesBadge = (passes: boolean | null) => {
    if (passes === true) {
      return (
        <Badge variant="default" className="bg-green-500/20 text-green-400 border-green-500/30">
          <CheckCircle2 className="mr-1 h-3 w-3" />
          Verified
        </Badge>
      );
    }
    if (passes === false) {
      return (
        <Badge variant="default" className="bg-red-500/20 text-red-400 border-red-500/30">
          <XCircle className="mr-1 h-3 w-3" />
          Failing
        </Badge>
      );
    }
    return (
      <Badge variant="default" className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
        <HelpCircle className="mr-1 h-3 w-3" />
        Unreviewed
      </Badge>
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold">{summaryData?.total || 0}</div>
          <div className="text-sm text-muted-foreground">Total Features</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-green-400">
            {summaryData?.passes_breakdown?.passing || 0}
          </div>
          <div className="text-sm text-muted-foreground">Verified</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-red-400">
            {summaryData?.passes_breakdown?.failing || 0}
          </div>
          <div className="text-sm text-muted-foreground">Failing</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-yellow-400">
            {summaryData?.passes_breakdown?.unreviewed || 0}
          </div>
          <div className="text-sm text-muted-foreground">Unreviewed</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[250px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search features..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>

        {categories.length > 0 && (
          <Select value={categoryFilter} onValueChange={(v) => { setCategoryFilter(v); setCurrentPage(1); }}>
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

        <Select value={passesFilter} onValueChange={(v) => { setPassesFilter(v); setCurrentPage(1); }}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="true">Verified</SelectItem>
            <SelectItem value="false">Failing</SelectItem>
            <SelectItem value="null">Unreviewed</SelectItem>
          </SelectContent>
        </Select>

        <Select value={String(pageSize)} onValueChange={handlePageSizeChange}>
          <SelectTrigger className="w-[80px]">
            <SelectValue placeholder="25" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="10">10</SelectItem>
            <SelectItem value="25">25</SelectItem>
            <SelectItem value="50">50</SelectItem>
            <SelectItem value="100">100</SelectItem>
            <SelectItem value="200">200</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Results count */}
      <div className="text-sm text-muted-foreground">
        {totalFiltered > 0
          ? `Showing ${startIndex + 1}–${endIndex} of ${totalFiltered} features`
          : "No features match your filters"}
        {totalFiltered > 0 && totalFiltered !== (featuresData?.total || 0) && ` (filtered from ${featuresData?.total || 0})`}
      </div>

      {/* Table */}
      {paginatedFeatures.length > 0 ? (
        <div className="rounded-lg border border-border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="px-2 w-20">ID</TableHead>
                <TableHead className="px-2 w-40">Name</TableHead>
                <TableHead className="px-2 w-48">Description</TableHead>
                <TableHead className="px-2 w-24">Category</TableHead>
                <TableHead className="px-2 w-32">Layers</TableHead>
                <TableHead className="px-2 w-12 text-center">Tests</TableHead>
                <TableHead className="px-2 w-24">Status</TableHead>
                <TableHead className="px-2 w-20 text-right">Progress</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedFeatures.map((feature) => {
                const isExpanded = expandedRows.has(feature.feature_id);
                const hasTasks = feature.tasks && feature.tasks.length > 0;

                return (
                  <Fragment key={feature.feature_id}>
                    <TableRow
                      className={hasTasks ? "cursor-pointer hover:bg-muted/50" : ""}
                      onClick={() => hasTasks && toggleRow(feature.feature_id)}
                      style={{ backgroundColor: getRowBgColor(feature.passes) }}
                    >
                      <TableCell className="font-mono text-xs px-2 align-top py-2 w-20">
                        <div className="flex items-center gap-1">
                          <span className="w-4 h-4 inline-flex items-center justify-center shrink-0">
                            {hasTasks && (
                              isExpanded ? (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                              )
                            )}
                          </span>
                          <span
                            style={{
                              color: feature.passes === true
                                ? "#4ade80"  // green-400
                                : feature.passes === false
                                ? "#f87171"  // red-400
                                : "#a1a1aa", // zinc-400
                            }}
                          >
                            {feature.feature_id}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-40">
                        <div className="flex items-center gap-1">
                          {feature.needs_review && (
                            <span
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ backgroundColor: "#f59e0b" }}
                              title="Needs review"
                            />
                          )}
                          <span className="font-medium truncate" title={feature.name}>
                            {feature.name}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-48">
                        <div className="text-sm text-muted-foreground whitespace-normal break-words">
                          {feature.description || "—"}
                        </div>
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-24">
                        {feature.category && (() => {
                          const colors = categoryColors[feature.category] || defaultCategoryColor;
                          return (
                            <span
                              className="text-xs px-1.5 py-0.5 rounded border"
                              style={{
                                backgroundColor: colors.bg,
                                color: colors.text,
                                borderColor: colors.border,
                              }}
                            >
                              {feature.category}
                            </span>
                          );
                        })()}
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-32">
                        <div className="flex flex-wrap gap-0.5">
                          {feature.layers?.map((layer) => {
                            const result = feature.layer_results?.[layer];
                            // Green for passed, red for failed, blue-gray for unverified
                            const bgColor = result?.passed === true
                              ? "#22c55e"  // green-500 (brighter)
                              : result?.passed === false
                              ? "#ef4444"  // red-500 (brighter)
                              : "#475569"; // slate-600 (visible gray)
                            const borderColor = result?.passed === true
                              ? "#16a34a"  // green-600
                              : result?.passed === false
                              ? "#dc2626"  // red-600
                              : "#64748b"; // slate-500
                            const textColor = "#ffffff";
                            return (
                              <span
                                key={layer}
                                className="text-[10px] px-1 rounded border"
                                style={{
                                  backgroundColor: bgColor,
                                  color: textColor,
                                  borderColor: borderColor,
                                }}
                                title={result?.evidence || `${layer} - not verified`}
                              >
                                {layer}
                              </span>
                            );
                          })}
                          {(!feature.layers || feature.layers.length === 0) && (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="px-2 text-center align-top py-2 w-12">
                        <span style={{ color: feature.test_count > 0 ? "#4ade80" : "#71717a" }}>
                          {feature.test_count}
                        </span>
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-24">{renderPassesBadge(feature.passes)}</TableCell>
                      <TableCell className="px-2 text-right align-top py-2 w-20">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-10 h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className={`h-full ${
                                feature.completion_pct === 100
                                  ? "bg-green-500"
                                  : feature.completion_pct > 0
                                  ? "bg-yellow-500"
                                  : "bg-muted-foreground"
                              }`}
                              style={{ width: `${feature.completion_pct}%` }}
                            />
                          </div>
                          <span
                            className="text-xs"
                            style={{
                              color: feature.completion_pct === 100
                                ? "#4ade80"  // green-400
                                : feature.completion_pct > 0
                                ? "#facc15"  // yellow-400
                                : "#71717a", // zinc-500
                            }}
                          >
                            {feature.completed_tasks}/{feature.total_tasks}
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                    {/* Expanded subtasks row */}
                    {isExpanded && hasTasks && (
                      <TableRow key={`${feature.feature_id}-tasks`} className="bg-muted/30">
                        <TableCell colSpan={8} className="py-2 px-4">
                          <div className="pl-6 space-y-1">
                            <div className="text-xs font-medium text-muted-foreground mb-2">
                              Subtasks ({feature.completed_tasks}/{feature.total_tasks})
                            </div>
                            {feature.tasks.map((task) => (
                              <div
                                key={task.task_id}
                                className="flex items-center gap-2 py-1"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <Checkbox
                                  checked={task.completed}
                                  onCheckedChange={(checked) =>
                                    toggleTask(feature.feature_id, task.task_id, checked as boolean)
                                  }
                                  className="shrink-0"
                                />
                                <span className="font-mono text-xs text-muted-foreground shrink-0 min-w-[100px]">
                                  {task.task_id}
                                </span>
                                <span className={`flex-1 ${task.completed ? "line-through text-muted-foreground" : ""}`}>
                                  {task.description}
                                </span>
                                {task.completed_by && (
                                  <span className="text-xs text-muted-foreground ml-2 shrink-0">
                                    by {task.completed_by}
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div className="rounded-lg border border-border bg-surface p-8 text-center">
          <FileText className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
          <p className="mt-4 text-sm text-muted-foreground">
            No features found. Use /task_it to add features.
          </p>
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-4">
          <div className="text-sm text-muted-foreground">
            Page {currentPage} of {totalPages}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
