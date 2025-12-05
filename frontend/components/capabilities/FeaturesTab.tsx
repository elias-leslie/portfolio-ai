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
import {
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
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

  // Fetch features
  const { data: featuresData, isLoading } = useQuery<FeaturesResponse>({
    queryKey: ["features", categoryFilter, passesFilter],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (categoryFilter !== "all") params.set("category", categoryFilter);
      if (passesFilter !== "all") params.set("passes", passesFilter);
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

  // Get unique categories
  const categories = summaryData?.category_breakdown
    ? Object.keys(summaryData.category_breakdown).sort()
    : [];

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
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

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

        <Select value={passesFilter} onValueChange={setPassesFilter}>
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
      </div>

      {/* Results count */}
      <div className="text-sm text-muted-foreground">
        Showing {filteredFeatures.length} of {featuresData?.total || 0} features
      </div>

      {/* Table */}
      {filteredFeatures.length > 0 ? (
        <div className="rounded-lg border border-border overflow-x-auto">
          <Table className="w-full">
            <TableHeader>
              <TableRow>
                <TableHead className="px-3 whitespace-nowrap">ID</TableHead>
                <TableHead className="px-3 whitespace-nowrap">Name</TableHead>
                <TableHead className="px-3 min-w-[150px] max-w-[400px]">Description</TableHead>
                <TableHead className="px-3 whitespace-nowrap">Category</TableHead>
                <TableHead className="px-3 whitespace-nowrap">Status</TableHead>
                <TableHead className="px-3 whitespace-nowrap text-right">Progress</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredFeatures.map((feature) => {
                const isExpanded = expandedRows.has(feature.feature_id);
                const hasTasks = feature.tasks && feature.tasks.length > 0;

                return (
                  <Fragment key={feature.feature_id}>
                    <TableRow
                      className={hasTasks ? "cursor-pointer hover:bg-muted/50" : ""}
                      onClick={() => hasTasks && toggleRow(feature.feature_id)}
                    >
                      <TableCell className="font-mono text-xs px-3 whitespace-nowrap">
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
                          {feature.feature_id}
                        </div>
                      </TableCell>
                      <TableCell className="px-3 whitespace-nowrap">
                        <div className="font-medium">
                          {feature.name}
                        </div>
                      </TableCell>
                      <TableCell className="px-3 max-w-[400px]">
                        <div className="text-sm text-muted-foreground truncate" title={feature.description || ""}>
                          {feature.description || "—"}
                        </div>
                      </TableCell>
                      <TableCell className="px-3 whitespace-nowrap">
                        {feature.category && (
                          <Badge variant="outline">{feature.category}</Badge>
                        )}
                      </TableCell>
                      <TableCell className="px-3 whitespace-nowrap">{renderPassesBadge(feature.passes)}</TableCell>
                      <TableCell className="px-3 whitespace-nowrap text-right">
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
                          <span className="text-xs text-muted-foreground">
                            {feature.completed_tasks}/{feature.total_tasks}
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                    {/* Expanded subtasks row */}
                    {isExpanded && hasTasks && (
                      <TableRow key={`${feature.feature_id}-tasks`} className="bg-muted/30">
                        <TableCell colSpan={6} className="py-2 px-4">
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
    </div>
  );
}
