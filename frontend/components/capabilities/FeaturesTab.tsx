"use client";

import { useState, Fragment, useMemo } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
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
  Play,
  Target,
  Eye,
  BookOpen,
  Code,
  AlertTriangle,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Download,
} from "lucide-react";
import { EvidenceViewerModal } from "./EvidenceViewerModal";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Highlight search matches in text
 */
function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query || !text) return <>{text}</>;

  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark key={i} className="bg-accent/40 text-accent-foreground rounded px-0.5">
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </>
  );
}

/**
 * Skeleton loading for FeaturesTab
 */
function FeaturesTabSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading features...">
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-lg border border-border bg-surface p-4">
            <Skeleton className="h-8 w-16 mb-2" />
            <Skeleton className="h-4 w-24" />
          </div>
        ))}
      </div>

      {/* Verification Summary */}
      <div className="rounded-lg border border-border bg-surface p-4">
        <Skeleton className="h-5 w-48 mb-3" />
        <div className="grid grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              <Skeleton className="h-4 w-4 rounded" />
              <Skeleton className="h-6 w-12" />
            </div>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Skeleton className="h-10 flex-1 min-w-[250px]" />
        <Skeleton className="h-10 w-[180px]" />
        <Skeleton className="h-10 w-[160px]" />
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border">
        <div className="p-4 space-y-3">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-8" />
              <Skeleton className="h-4 w-8" />
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-6 w-20" />
              <Skeleton className="h-4 w-16 ml-auto" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Task interface for subtasks
interface Task {
  id: number | null;
  task_id: string;
  description: string;
  completed: boolean;
  order_num: number;
  completed_at: string | null;
  completed_by: string | null;
  // Enhanced fields
  files: string[];
  notes: string | null;
  status: string;
  effort: string | null;
  task_type: string;  // implementation, fix, task_file, discovery
}

// Acceptance Criterion interface (matches backend AcceptanceCriterion model)
interface AcceptanceCriterion {
  id: string;
  criterion: string;
  verification: string;
  type: string;
  passed: boolean | null;
  // Verification tracking fields (added for auto-verification)
  verified_at: string | null;
  verified_by: string | null; // auto, manual, pytest, browser
  verification_output: string | null;
}

// Implementation Notes interface for structured task file replacement
interface ImplementationNotes {
  steps?: string[];
  files?: string[];
  examples?: { code?: string; description?: string };
  blockers?: string[];
  notes?: string;
  context?: string;
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
  // New spec-driven fields
  priority: number | null;
  effective_priority: number;
  acceptance_criteria: AcceptanceCriterion[];
  vision_goals: string[];
  implementation_notes: ImplementationNotes;
  // Enhanced fields for task file replacement
  status: string;
  effort: string | null;
  source: string | null;
  diagram: string | null;
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

interface VerificationSummary {
  total_criteria: number;
  passed: number;
  failed: number;
  pending: number;
  by_type: Record<string, { total: number; passed: number; failed: number; pending: number }>;
}

interface VisionGoal {
  code: string;
  name: string;
  description: string | null;
  category: string | null;
}

// Sorting types
type SortColumn = "feature_id" | "priority" | "effort" | "name" | "category" | "last_verified_at" | "criteria" | "passes" | "progress";
type SortDirection = "asc" | "desc";

export function FeaturesTab() {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [passesFilter, setPassesFilter] = useState("all");
  const [visionGoalFilter, setVisionGoalFilter] = useState("all");
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [pageSize, setPageSize] = useState(25);
  const [currentPage, setCurrentPage] = useState(1);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyTypeFilter, setVerifyTypeFilter] = useState("api");
  const [sortColumn, setSortColumn] = useState<SortColumn>("feature_id");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [evidenceModal, setEvidenceModal] = useState<{
    open: boolean;
    featureId: string;
    criterionId: string;
    criterionText: string;
    verificationUrl: string;
  }>({ open: false, featureId: "", criterionId: "", criterionText: "", verificationUrl: "" });

  // Parse URL from verification text like "screenshot /agents showing..."
  const parseVerificationUrl = (verification: string): string => {
    const match = verification.match(/screenshot\s+(\/[^\s]+)/i);
    if (match) {
      return `http://192.168.8.233:3000${match[1]}`;
    }
    return "";
  };
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

  // Fetch features - first get total, then fetch all, then fetch gaps
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

      // Fetch all features (max 500 per backend API limit)
      params.set("limit", String(Math.min(total, 500)));
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

  // Fetch verification summary for criteria status
  const { data: verificationData } = useQuery<VerificationSummary>({
    queryKey: ["verification-summary"],
    queryFn: async () => {
      const response = await fetch("/api/capabilities/features/verification-summary");
      if (!response.ok) throw new Error("Failed to fetch verification summary");
      return response.json();
    },
  });

  // Fetch vision goals for filter dropdown
  const { data: visionGoalsData } = useQuery<VisionGoal[]>({
    queryKey: ["vision-goals"],
    queryFn: async () => {
      const response = await fetch("/api/vision-goals");
      if (!response.ok) throw new Error("Failed to fetch vision goals");
      return response.json();
    },
  });

  // Verify all criteria function
  const handleVerifyAll = async () => {
    setIsVerifying(true);
    try {
      const params = verifyTypeFilter !== "all" ? `?type_filter=${verifyTypeFilter}` : "";
      const response = await fetch(`/api/capabilities/features/verify-all${params}`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Failed to start verification");
      const data = await response.json();
      toast.success(`Verification queued: ${data.task_id.slice(0, 8)}...`);
      // Poll for completion
      const pollInterval = setInterval(async () => {
        const summaryRes = await fetch("/api/capabilities/features/verification-summary");
        if (summaryRes.ok) {
          queryClient.invalidateQueries({ queryKey: ["verification-summary"] });
        }
      }, 5000);
      // Stop polling after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        setIsVerifying(false);
        queryClient.invalidateQueries({ queryKey: ["verification-summary"] });
        toast.success("Verification complete");
      }, 120000);
    } catch {
      toast.error("Failed to start verification");
      setIsVerifying(false);
    }
  };

  // Toggle sort column/direction
  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortColumn(column);
      setSortDirection("asc");
    }
    setCurrentPage(1);
  };

  // Get sort icon for column header
  const getSortIcon = (column: SortColumn) => {
    if (sortColumn !== column) {
      return <ArrowUpDown className="h-3 w-3 ml-1 opacity-40" />;
    }
    return sortDirection === "asc"
      ? <ArrowUp className="h-3 w-3 ml-1" />
      : <ArrowDown className="h-3 w-3 ml-1" />;
  };

  // Filter features by search query and vision goal
  const filteredFeatures = featuresData?.features.filter((f) => {
    // Vision goal filter
    if (visionGoalFilter !== "all") {
      if (!f.vision_goals || !f.vision_goals.includes(visionGoalFilter)) {
        return false;
      }
    }
    // Search filter
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      f.feature_id.toLowerCase().includes(q) ||
      f.name.toLowerCase().includes(q) ||
      f.category?.toLowerCase().includes(q) ||
      f.description?.toLowerCase().includes(q)
    );
  }) ?? [];

  // Sort features
  const sortedFeatures = [...filteredFeatures].sort((a, b) => {
    let comparison = 0;

    switch (sortColumn) {
      case "feature_id":
        // Natural sort for IDs like FEAT-001, FEAT-002, FEAT-GAP-001
        comparison = a.feature_id.localeCompare(b.feature_id, undefined, { numeric: true });
        break;
      case "priority":
        comparison = (a.priority ?? a.effective_priority) - (b.priority ?? b.effective_priority);
        break;
      case "effort": {
        const effortOrder: Record<string, number> = { low: 1, medium: 2, high: 3, very_high: 4 };
        const aEffort = effortOrder[a.effort ?? ""] ?? 5;
        const bEffort = effortOrder[b.effort ?? ""] ?? 5;
        comparison = aEffort - bEffort;
        break;
      }
      case "name":
        comparison = a.name.localeCompare(b.name);
        break;
      case "category":
        comparison = (a.category ?? "").localeCompare(b.category ?? "");
        break;
      case "last_verified_at": {
        const aDate = a.last_verified_at ? new Date(a.last_verified_at).getTime() : 0;
        const bDate = b.last_verified_at ? new Date(b.last_verified_at).getTime() : 0;
        comparison = aDate - bDate;
        break;
      }
      case "criteria": {
        const aPassed = a.acceptance_criteria?.filter(c => c.passed === true).length ?? 0;
        const bPassed = b.acceptance_criteria?.filter(c => c.passed === true).length ?? 0;
        const aTotal = a.acceptance_criteria?.length ?? 0;
        const bTotal = b.acceptance_criteria?.length ?? 0;
        // Sort by ratio, then by total
        const aRatio = aTotal > 0 ? aPassed / aTotal : 0;
        const bRatio = bTotal > 0 ? bPassed / bTotal : 0;
        comparison = aRatio - bRatio || aTotal - bTotal;
        break;
      }
      case "passes": {
        // null=0, false=1, true=2 for ascending (unreviewed first, then failing, then verified)
        const passesOrder = (p: boolean | null) => p === null ? 0 : p === false ? 1 : 2;
        comparison = passesOrder(a.passes) - passesOrder(b.passes);
        break;
      }
      case "progress":
        comparison = a.completion_pct - b.completion_pct;
        break;
      default:
        comparison = 0;
    }

    return sortDirection === "asc" ? comparison : -comparison;
  });

  // Pagination calculations
  const totalFiltered = sortedFeatures.length;
  const totalPages = Math.ceil(totalFiltered / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalFiltered);
  const paginatedFeatures = sortedFeatures.slice(startIndex, endIndex);

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

  // Render verified status badge
  // Logic: "Verified" only when tasks=0 AND all criteria passed
  const renderPassesBadge = (feature: Feature) => {
    const incompleteTasks = feature.total_tasks - feature.completed_tasks;
    const criteria = feature.acceptance_criteria || [];
    const allCriteriaPassed = criteria.length > 0 && criteria.every(c => c.passed === true);
    const hasCriteria = criteria.length > 0;

    // Has incomplete tasks - show "Has Tasks"
    if (incompleteTasks > 0) {
      return (
        <Badge variant="default" className="bg-orange-500/20 text-orange-400 border-orange-500/30">
          <AlertTriangle className="mr-1 h-3 w-3" />
          Has Tasks
        </Badge>
      );
    }

    // No criteria defined - show "No Criteria"
    if (!hasCriteria) {
      return (
        <Badge variant="default" className="bg-zinc-500/20 text-zinc-400 border-zinc-500/30">
          <HelpCircle className="mr-1 h-3 w-3" />
          No Criteria
        </Badge>
      );
    }

    // Tasks=0, has criteria, all passed - show "Verified"
    if (allCriteriaPassed) {
      return (
        <Badge variant="default" className="bg-green-500/20 text-green-400 border-green-500/30">
          <CheckCircle2 className="mr-1 h-3 w-3" />
          Verified
        </Badge>
      );
    }

    // Tasks=0, has criteria, not all passed - show "Needs Review"
    return (
      <Badge variant="default" className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
        <HelpCircle className="mr-1 h-3 w-3" />
        Needs Review
      </Badge>
    );
  };

  // Render priority badge (P1-P5 with colors)
  const renderPriorityBadge = (priority: number | null, effectivePriority: number) => {
    const p = priority ?? effectivePriority;
    const colors: Record<number, { bg: string; text: string; border: string }> = {
      1: { bg: "#ef444420", text: "#f87171", border: "#ef444440" }, // red - critical
      2: { bg: "#f9731620", text: "#fb923c", border: "#f9731640" }, // orange
      3: { bg: "#eab30820", text: "#facc15", border: "#eab30840" }, // yellow
      4: { bg: "#3b82f620", text: "#60a5fa", border: "#3b82f640" }, // blue
      5: { bg: "#71717a20", text: "#a1a1aa", border: "#71717a40" }, // gray
    };
    const color = colors[p] || colors[5];
    return (
      <span
        className="text-xs px-1.5 py-0.5 rounded border font-medium"
        style={{
          backgroundColor: color.bg,
          color: color.text,
          borderColor: color.border,
        }}
      >
        P{p}
      </span>
    );
  };

  // Render criteria status (X/Y format)
  const renderCriteriaStatus = (criteria: AcceptanceCriterion[]) => {
    if (!criteria || criteria.length === 0) {
      return <span className="text-xs text-muted-foreground">—</span>;
    }
    const passed = criteria.filter((c) => c.passed === true).length;
    const total = criteria.length;
    const allPassed = passed === total;
    const hasFailed = criteria.some((c) => c.passed === false);

    return (
      <span
        className="text-xs font-mono"
        style={{
          color: allPassed ? "#4ade80" : hasFailed ? "#f87171" : "#a1a1aa",
        }}
      >
        {passed}/{total}
      </span>
    );
  };

  // Render effort badge
  const renderEffortBadge = (effort: string | null) => {
    if (!effort) return <span className="text-xs text-muted-foreground">—</span>;
    const colors: Record<string, { bg: string; text: string; border: string }> = {
      low: { bg: "#22c55e20", text: "#4ade80", border: "#22c55e40" },
      medium: { bg: "#eab30820", text: "#facc15", border: "#eab30840" },
      high: { bg: "#f9731620", text: "#fb923c", border: "#f9731640" },
      very_high: { bg: "#ef444420", text: "#f87171", border: "#ef444440" },
    };
    const color = colors[effort] || colors.medium;
    const labels: Record<string, string> = {
      low: "L",
      medium: "M",
      high: "H",
      very_high: "VH",
    };
    return (
      <span
        className="text-[10px] px-1 py-0.5 rounded border font-medium"
        style={{ backgroundColor: color.bg, color: color.text, borderColor: color.border }}
        title={`Effort: ${effort}`}
      >
        {labels[effort] || effort}
      </span>
    );
  };

  // Format relative time (e.g., "2h ago", "3d ago")
  const formatRelativeTime = (dateString: string | null): string => {
    if (!dateString) return "—";
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return "now";
    if (diffMins < 60) return `${diffMins}m`;
    if (diffHours < 24) return `${diffHours}h`;
    if (diffDays < 30) return `${diffDays}d`;
    return `${Math.floor(diffDays / 30)}mo`;
  };

  // Export features to CSV
  const handleExportCSV = () => {
    if (!sortedFeatures.length) return;

    const headers = ["Feature ID", "Name", "Category", "Status", "Priority", "Effort", "Progress %", "Tasks Completed", "Total Tasks", "Criteria Passed", "Total Criteria"];
    const rows = sortedFeatures.map(f => [
      f.feature_id,
      f.name,
      f.category || "",
      f.passes === true ? "Verified" : f.passes === false ? "Failing" : "Unreviewed",
      String(f.priority ?? f.effective_priority),
      f.effort || "",
      String(f.completion_pct),
      String(f.completed_tasks),
      String(f.total_tasks),
      String(f.acceptance_criteria?.filter(c => c.passed === true).length ?? 0),
      String(f.acceptance_criteria?.length ?? 0),
    ]);

    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `features-export-${new Date().toISOString().split("T")[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success("Features exported to CSV");
  };

  // Export features to JSON
  const handleExportJSON = () => {
    if (!sortedFeatures.length) return;

    const exportData = sortedFeatures.map(f => ({
      feature_id: f.feature_id,
      name: f.name,
      category: f.category,
      status: f.passes === true ? "verified" : f.passes === false ? "failing" : "unreviewed",
      priority: f.priority ?? f.effective_priority,
      effort: f.effort,
      completion_pct: f.completion_pct,
      completed_tasks: f.completed_tasks,
      total_tasks: f.total_tasks,
      criteria_passed: f.acceptance_criteria?.filter(c => c.passed === true).length ?? 0,
      criteria_total: f.acceptance_criteria?.length ?? 0,
      vision_goals: f.vision_goals,
    }));

    const json = JSON.stringify(exportData, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `features-export-${new Date().toISOString().split("T")[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success("Features exported to JSON");
  };

  if (isLoading) {
    return <FeaturesTabSkeleton />;
  }

  return (
    <div className="space-y-4">
      {/* Summary Cards - Features */}
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

      {/* Acceptance Criteria Summary */}
      {verificationData && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium">Acceptance Criteria Verification</span>
            <div className="flex items-center gap-2">
              <Select value={verifyTypeFilter} onValueChange={setVerifyTypeFilter}>
                <SelectTrigger className="w-[100px] h-7 text-xs">
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="api">API</SelectItem>
                  <SelectItem value="ui">UI</SelectItem>
                  <SelectItem value="test">Test</SelectItem>
                </SelectContent>
              </Select>
              <Button
                size="sm"
                variant="outline"
                onClick={handleVerifyAll}
                disabled={isVerifying}
                className="h-7 text-xs"
              >
                {isVerifying ? (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                ) : (
                  <Play className="h-3 w-3 mr-1" />
                )}
                {isVerifying ? "Verifying..." : "Verify All"}
              </Button>
              <span className="text-xs text-muted-foreground">{verificationData.total_criteria} total</span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-400" />
              <div>
                <span className="text-lg font-semibold text-green-400">{verificationData.passed}</span>
                <span className="text-xs text-muted-foreground ml-1">passed</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-400" />
              <div>
                <span className="text-lg font-semibold text-red-400">{verificationData.failed}</span>
                <span className="text-xs text-muted-foreground ml-1">failed</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4 text-yellow-500" />
              <div>
                <span className="text-lg font-semibold text-yellow-400">{verificationData.pending}</span>
                <span className="text-xs text-muted-foreground ml-1">pending</span>
              </div>
            </div>
          </div>
          {verificationData.by_type && Object.keys(verificationData.by_type).length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/50 flex gap-4 text-xs">
              {Object.entries(verificationData.by_type).map(([type, stats]) => (
                <span key={type} className="text-muted-foreground">
                  <span className="capitalize">{type}</span>:{" "}
                  <span className="text-green-400">{stats.passed}</span>/
                  <span>{stats.total}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

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

        {visionGoalsData && visionGoalsData.length > 0 && (
          <Select value={visionGoalFilter} onValueChange={(v) => { setVisionGoalFilter(v); setCurrentPage(1); }}>
            <SelectTrigger className="w-[180px]">
              <Target className="mr-2 h-4 w-4" />
              <SelectValue placeholder="Vision Goal" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Vision Goals</SelectItem>
              {visionGoalsData.map((goal) => (
                <SelectItem key={goal.code} value={goal.code}>
                  {goal.code}: {goal.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

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

        {/* Export buttons */}
        <div className="flex gap-1 ml-auto">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExportCSV}
                  disabled={!sortedFeatures.length}
                  aria-label="Export to CSV"
                >
                  <Download className="h-4 w-4 mr-1" />
                  CSV
                </Button>
              </TooltipTrigger>
              <TooltipContent>Export filtered features to CSV</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExportJSON}
                  disabled={!sortedFeatures.length}
                  aria-label="Export to JSON"
                >
                  <Download className="h-4 w-4 mr-1" />
                  JSON
                </Button>
              </TooltipTrigger>
              <TooltipContent>Export filtered features to JSON</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
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
                <TableHead
                  className="px-2 w-20 cursor-pointer hover:bg-muted/50 select-none"
                  onClick={() => handleSort("feature_id")}
                >
                  <div className="flex items-center">
                    ID{getSortIcon("feature_id")}
                  </div>
                </TableHead>
                <TableHead
                  className="px-2 w-10 text-center cursor-pointer hover:bg-muted/50 select-none"
                  onClick={() => handleSort("priority")}
                >
                  <div className="flex items-center justify-center">
                    P{getSortIcon("priority")}
                  </div>
                </TableHead>
                <TableHead
                  className="px-2 w-8 text-center cursor-pointer hover:bg-muted/50 select-none"
                  onClick={() => handleSort("effort")}
                >
                  <div className="flex items-center justify-center">
                    E{getSortIcon("effort")}
                  </div>
                </TableHead>
                <TableHead
                  className="px-2 w-40 cursor-pointer hover:bg-muted/50 select-none"
                  onClick={() => handleSort("name")}
                >
                  <div className="flex items-center">
                    Name{getSortIcon("name")}
                  </div>
                </TableHead>
                <TableHead
                  className="px-2 w-24 cursor-pointer hover:bg-muted/50 select-none"
                  onClick={() => handleSort("category")}
                >
                  <div className="flex items-center">
                    Category{getSortIcon("category")}
                  </div>
                </TableHead>
                <TableHead
                  className="px-2 w-16 text-center cursor-pointer hover:bg-muted/50 select-none"
                  onClick={() => handleSort("last_verified_at")}
                >
                  <div className="flex items-center justify-center">
                    Checked{getSortIcon("last_verified_at")}
                  </div>
                </TableHead>
                <TableHead
                  className="px-2 w-14 text-center cursor-pointer hover:bg-muted/50 select-none"
                  onClick={() => handleSort("criteria")}
                >
                  <div className="flex items-center justify-center">
                    Criteria{getSortIcon("criteria")}
                  </div>
                </TableHead>
                <TableHead
                  className="px-2 w-24 cursor-pointer hover:bg-muted/50 select-none"
                  onClick={() => handleSort("passes")}
                >
                  <div className="flex items-center">
                    Verified{getSortIcon("passes")}
                  </div>
                </TableHead>
                <TableHead
                  className="px-2 w-20 text-right cursor-pointer hover:bg-muted/50 select-none"
                  onClick={() => handleSort("progress")}
                >
                  <div className="flex items-center justify-end">
                    Tasks{getSortIcon("progress")}
                  </div>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedFeatures.map((feature) => {
                const isExpanded = expandedRows.has(feature.feature_id);
                const hasTasks = feature.tasks && feature.tasks.length > 0;

                return (
                  <Fragment key={feature.feature_id}>
                    <TableRow
                      className={(hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0)) ? "cursor-pointer hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-accent" : ""}
                      onClick={() => (hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0)) && toggleRow(feature.feature_id)}
                      onKeyDown={(e) => {
                        if ((e.key === "Enter" || e.key === " ") && (hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0))) {
                          e.preventDefault();
                          toggleRow(feature.feature_id);
                        }
                      }}
                      tabIndex={(hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0)) ? 0 : -1}
                      role="row"
                      aria-expanded={(hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0)) ? isExpanded : undefined}
                      style={{ backgroundColor: getRowBgColor(feature.passes) }}
                    >
                      <TableCell className="font-mono text-xs px-2 align-top py-2 w-20">
                        <div className="flex items-center gap-1">
                          <span
                            className="w-4 h-4 inline-flex items-center justify-center shrink-0"
                            aria-hidden="true"
                          >
                            {(hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0)) && (
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
                            <HighlightMatch text={feature.feature_id} query={searchQuery} />
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-10 text-center">
                        {renderPriorityBadge(feature.priority, feature.effective_priority)}
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-8 text-center">
                        {renderEffortBadge(feature.effort)}
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-40">
                        <div className="flex items-center gap-1">
                          {feature.needs_review && (
                            <span
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ backgroundColor: "#f59e0b" }}
                              title="Needs review"
                              aria-label="Needs review"
                            />
                          )}
                          <span className="font-medium truncate" title={feature.name}>
                            <HighlightMatch text={feature.name} query={searchQuery} />
                          </span>
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
                      <TableCell className="px-2 align-top py-2 w-16 text-center">
                        <span
                          className="text-xs text-muted-foreground"
                          title={feature.last_verified_at ? new Date(feature.last_verified_at).toLocaleString() : "Never verified"}
                        >
                          {formatRelativeTime(feature.last_verified_at)}
                        </span>
                      </TableCell>
                      <TableCell className="px-2 text-center align-top py-2 w-14">
                        {renderCriteriaStatus(feature.acceptance_criteria)}
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-24">{renderPassesBadge(feature)}</TableCell>
                      <TableCell className="px-2 text-right align-top py-2 w-20">
                        {(() => {
                          const incompleteTasks = feature.total_tasks - feature.completed_tasks;
                          return (
                            <span
                              className="text-xs font-mono"
                              style={{
                                color: incompleteTasks === 0
                                  ? "#4ade80"  // green-400 (no tasks)
                                  : "#facc15", // yellow-400 (has tasks)
                              }}
                              title={`${feature.completed_tasks}/${feature.total_tasks} completed`}
                            >
                              {incompleteTasks}
                            </span>
                          );
                        })()}
                      </TableCell>
                    </TableRow>
                    {/* Expanded details row (subtasks + acceptance criteria) */}
                    {isExpanded && (hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0)) && (
                      <TableRow key={`${feature.feature_id}-details`} className="bg-muted/30">
                        <TableCell colSpan={9} className="py-2 px-4">
                          <div className="pl-6 space-y-4">
                            {/* Acceptance Criteria Section */}
                            {feature.acceptance_criteria && feature.acceptance_criteria.length > 0 && (
                              <div className="space-y-1">
                                <div className="flex items-center justify-between mb-3">
                                  <span className="text-xs font-medium text-muted-foreground">
                                    Acceptance Criteria ({feature.acceptance_criteria.filter(c => c.passed === true).length}/{feature.acceptance_criteria.length} verified)
                                  </span>
                                  <span className="text-[10px] text-muted-foreground/70 flex items-center gap-3">
                                    <span className="flex items-center gap-0.5"><CheckCircle2 className="h-3 w-3 text-green-400" />pass</span>
                                    <span className="flex items-center gap-0.5"><XCircle className="h-3 w-3 text-red-400" />fail</span>
                                    <span className="flex items-center gap-0.5"><HelpCircle className="h-3 w-3 text-yellow-500" />pending</span>
                                  </span>
                                </div>
                                {feature.acceptance_criteria.map((criterion) => (
                                  <div
                                    key={criterion.id}
                                    className="py-2 border-b border-border/50 last:border-0"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <div className="flex items-start gap-2">
                                      <span
                                        className="shrink-0 mt-0.5"
                                        title={
                                          criterion.passed === true ? "Verified - Passed" :
                                          criterion.passed === false ? "Verified - Failed" :
                                          "Not yet verified (run /verify_it)"
                                        }
                                      >
                                        {criterion.passed === true ? (
                                          <CheckCircle2 className="h-4 w-4 text-green-400" />
                                        ) : criterion.passed === false ? (
                                          <XCircle className="h-4 w-4 text-red-400" />
                                        ) : (
                                          <HelpCircle className="h-4 w-4 text-yellow-500" />
                                        )}
                                      </span>
                                      <span className="font-mono text-xs text-muted-foreground shrink-0 min-w-[50px]">
                                        {criterion.id}
                                      </span>
                                      {criterion.type && (
                                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30 shrink-0">
                                          {criterion.type}
                                        </span>
                                      )}
                                      {criterion.type === "ui" && (
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          className="h-5 px-1.5 text-xs shrink-0"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setEvidenceModal({
                                              open: true,
                                              featureId: feature.feature_id,
                                              criterionId: criterion.id,
                                              criterionText: criterion.criterion,
                                              verificationUrl: parseVerificationUrl(criterion.verification || ""),
                                            });
                                          }}
                                        >
                                          <Eye className="h-3 w-3 mr-1" />
                                          Evidence
                                        </Button>
                                      )}
                                      <span className="flex-1 text-sm">
                                        {criterion.criterion}
                                      </span>
                                    </div>
                                    {criterion.verification && (
                                      <div className="mt-1 ml-6 pl-[50px]">
                                        <span className="text-xs text-muted-foreground">
                                          <span className="text-muted-foreground/60">Verify: </span>
                                          <code className="font-mono bg-muted/50 px-1 py-0.5 rounded text-[11px]">
                                            {criterion.verification}
                                          </code>
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                            {/* Vision Goals with Tooltips */}
                            {feature.vision_goals && feature.vision_goals.length > 0 && (
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">Vision Goals:</span>
                                <TooltipProvider>
                                  {feature.vision_goals.map((goalCode) => {
                                    const goalInfo = visionGoalsData?.find((g) => g.code === goalCode);
                                    return (
                                      <Tooltip key={goalCode}>
                                        <TooltipTrigger asChild>
                                          <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 border border-purple-500/30 cursor-help">
                                            {goalCode}
                                          </span>
                                        </TooltipTrigger>
                                        <TooltipContent>
                                          <div className="text-sm">
                                            <div className="font-medium">{goalInfo?.name || goalCode}</div>
                                            {goalInfo?.description && (
                                              <div className="text-xs text-muted-foreground mt-1 max-w-xs">
                                                {goalInfo.description}
                                              </div>
                                            )}
                                          </div>
                                        </TooltipContent>
                                      </Tooltip>
                                    );
                                  })}
                                </TooltipProvider>
                              </div>
                            )}
                            {/* Implementation Notes Section */}
                            {feature.implementation_notes && Object.keys(feature.implementation_notes).length > 0 && (
                              <div className="space-y-2 border-t border-border/50 pt-3">
                                <div className="flex items-center gap-2 mb-2">
                                  <BookOpen className="h-4 w-4 text-blue-400" />
                                  <span className="text-xs font-medium text-muted-foreground">Implementation Notes</span>
                                </div>
                                {/* Context */}
                                {feature.implementation_notes.context && (
                                  <div className="bg-muted/30 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Context</span>
                                    <p className="text-sm mt-1">{feature.implementation_notes.context}</p>
                                  </div>
                                )}
                                {/* Steps */}
                                {feature.implementation_notes.steps && feature.implementation_notes.steps.length > 0 && (
                                  <div className="bg-muted/30 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Steps</span>
                                    <ol className="list-decimal list-inside text-sm mt-1 space-y-0.5">
                                      {feature.implementation_notes.steps.map((step, idx) => (
                                        <li key={idx} className="text-sm">{step}</li>
                                      ))}
                                    </ol>
                                  </div>
                                )}
                                {/* Files */}
                                {feature.implementation_notes.files && feature.implementation_notes.files.length > 0 && (
                                  <div className="bg-muted/30 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground flex items-center gap-1">
                                      <Code className="h-3 w-3" /> Files to Modify
                                    </span>
                                    <div className="flex flex-wrap gap-1 mt-1">
                                      {feature.implementation_notes.files.map((file, idx) => (
                                        <code key={idx} className="text-xs bg-surface px-1.5 py-0.5 rounded font-mono text-blue-400">
                                          {file}
                                        </code>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {/* Blockers */}
                                {feature.implementation_notes.blockers && feature.implementation_notes.blockers.length > 0 && (
                                  <div className="bg-red-500/10 border border-red-500/20 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-red-400 flex items-center gap-1">
                                      <AlertTriangle className="h-3 w-3" /> Blockers
                                    </span>
                                    <ul className="list-disc list-inside text-sm mt-1 text-red-400">
                                      {feature.implementation_notes.blockers.map((blocker, idx) => (
                                        <li key={idx}>{blocker}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                {/* Notes */}
                                {feature.implementation_notes.notes && (
                                  <div className="bg-muted/30 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Notes</span>
                                    <p className="text-sm mt-1 whitespace-pre-wrap">{feature.implementation_notes.notes}</p>
                                  </div>
                                )}
                              </div>
                            )}
                            {/* Diagram Section */}
                            {feature.diagram && (
                              <div className="space-y-2 border-t border-border/50 pt-3">
                                <div className="flex items-center gap-2 mb-2">
                                  <Code className="h-4 w-4 text-cyan-400" />
                                  <span className="text-xs font-medium text-muted-foreground">Architecture Diagram</span>
                                </div>
                                <pre className="bg-muted/30 rounded p-3 text-xs font-mono overflow-x-auto whitespace-pre">
                                  {feature.diagram}
                                </pre>
                              </div>
                            )}
                            {/* Subtasks Section */}
                            {hasTasks && (
                              <div className="space-y-2 border-t border-border/50 pt-3">
                                <div className="text-xs font-medium text-muted-foreground mb-2">
                                  Subtasks ({feature.completed_tasks}/{feature.total_tasks})
                                </div>
                                {feature.tasks.map((task) => (
                                  <div
                                    key={task.task_id}
                                    className="bg-muted/20 rounded p-2 space-y-1"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <div className="flex items-center gap-2">
                                      <Checkbox
                                        checked={task.completed}
                                        onCheckedChange={(checked) =>
                                          toggleTask(feature.feature_id, task.task_id, checked as boolean)
                                        }
                                        className="shrink-0"
                                      />
                                      <span className="font-mono text-xs text-muted-foreground shrink-0 min-w-[50px]">
                                        {task.task_id}
                                      </span>
                                      {task.status && task.status !== "pending" && (
                                        <span
                                          className="text-[10px] px-1 py-0.5 rounded border shrink-0"
                                          style={{
                                            backgroundColor: task.status === "complete" ? "#22c55e20" : task.status === "in_progress" ? "#3b82f620" : task.status === "deferred" ? "#8b5cf620" : task.status === "blocked" ? "#ef444420" : "#71717a20",
                                            color: task.status === "complete" ? "#4ade80" : task.status === "in_progress" ? "#60a5fa" : task.status === "deferred" ? "#a78bfa" : task.status === "blocked" ? "#f87171" : "#a1a1aa",
                                            borderColor: task.status === "complete" ? "#22c55e40" : task.status === "in_progress" ? "#3b82f640" : task.status === "deferred" ? "#8b5cf640" : task.status === "blocked" ? "#ef444440" : "#71717a40",
                                          }}
                                        >
                                          {task.status}
                                        </span>
                                      )}
                                      {task.effort && (
                                        <span
                                          className="text-[10px] px-1 py-0.5 rounded border shrink-0"
                                          style={{
                                            backgroundColor: task.effort === "low" ? "#22c55e20" : task.effort === "medium" ? "#eab30820" : task.effort === "high" ? "#f9731620" : "#71717a20",
                                            color: task.effort === "low" ? "#4ade80" : task.effort === "medium" ? "#facc15" : task.effort === "high" ? "#fb923c" : "#a1a1aa",
                                            borderColor: task.effort === "low" ? "#22c55e40" : task.effort === "medium" ? "#eab30840" : task.effort === "high" ? "#f9731640" : "#71717a40",
                                          }}
                                        >
                                          {task.effort}
                                        </span>
                                      )}
                                      {task.task_type && task.task_type !== "implementation" && (
                                        <span
                                          className="text-[10px] px-1 py-0.5 rounded border shrink-0"
                                          style={{
                                            backgroundColor: task.task_type === "fix" ? "#ef444420" : task.task_type === "task_file" ? "#a855f720" : task.task_type === "discovery" ? "#f9731620" : "#71717a20",
                                            color: task.task_type === "fix" ? "#f87171" : task.task_type === "task_file" ? "#c084fc" : task.task_type === "discovery" ? "#fb923c" : "#a1a1aa",
                                            borderColor: task.task_type === "fix" ? "#ef444440" : task.task_type === "task_file" ? "#a855f740" : task.task_type === "discovery" ? "#f9731640" : "#71717a40",
                                          }}
                                        >
                                          {task.task_type}
                                        </span>
                                      )}
                                      <span className={`flex-1 ${task.completed ? "line-through text-muted-foreground" : ""}`}>
                                        {task.description}
                                      </span>
                                      {task.completed_by && (
                                        <span className="text-xs text-muted-foreground shrink-0">
                                          by {task.completed_by}
                                        </span>
                                      )}
                                    </div>
                                    {/* Subtask files */}
                                    {task.files && task.files.length > 0 && (
                                      <div className="ml-6 flex flex-wrap gap-1">
                                        {task.files.map((file, idx) => (
                                          <code key={idx} className="text-[10px] bg-surface px-1 py-0.5 rounded font-mono text-blue-400">
                                            {file}
                                          </code>
                                        ))}
                                      </div>
                                    )}
                                    {/* Subtask notes */}
                                    {task.notes && (
                                      <div className="ml-6 text-xs text-muted-foreground italic">
                                        {task.notes}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
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

      {/* Evidence Viewer Modal */}
      <EvidenceViewerModal
        open={evidenceModal.open}
        onOpenChange={(open) =>
          setEvidenceModal((prev) => ({ ...prev, open }))
        }
        featureId={evidenceModal.featureId}
        criterionId={evidenceModal.criterionId}
        criterionText={evidenceModal.criterionText}
        verificationUrl={evidenceModal.verificationUrl}
      />
    </div>
  );
}
