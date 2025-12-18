"use client";

import { useState, Fragment, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiRequest, post, patch } from "@/lib/api/client";

// SummitFlow API configuration
const SUMMITFLOW_API = "/summitflow/api/projects/portfolio-ai";
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
  taskId: string;
  description: string;
  completed: boolean;
  orderNum: number;
  completedAt: string | null;
  completedBy: string | null;
  // Enhanced fields
  files: string[];
  notes: string | null;
  status: string;
  effort: string | null;
  taskType: string;  // implementation, fix, taskFile, discovery
}

// Acceptance Criterion interface (matches backend AcceptanceCriterion model)
interface AcceptanceCriterion {
  id: string;
  criterion: string;
  verification: string;
  type: string;
  passed: boolean | null;
  // Verification tracking fields (added for auto-verification)
  verifiedAt: string | null;
  verifiedBy: string | null; // auto, manual, pytest, browser
  verificationOutput: string | null;
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
  featureId: string;
  name: string;
  category: string | null;
  description: string | null;
  layers: string[];
  layerResults: Record<string, { passed: boolean; evidence?: string }>;
  testCount: number;
  taskFile: string | null;
  taskSection: string | null;
  taskFileExists: boolean;
  totalTasks: number;
  completedTasks: number;
  completionPct: number;
  healthStatus: string;
  lastVerifiedAt: string | null;
  verifiedBy: string | null;
  tasks: Task[];
  // New spec-driven fields
  priority: number | null;
  effectivePriority: number;
  acceptanceCriteria: AcceptanceCriterion[];
  visionGoals: string[];
  implementationNotes: ImplementationNotes;
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
  passesBreakdown: Record<string, number>;
  categoryBreakdown: Record<string, number>;
  healthBreakdown: Record<string, number>;
}

interface VerificationSummary {
  totalCriteria: number;
  passed: number;
  failed: number;
  pending: number;
  byType: Record<string, { total: number; passed: number; failed: number; pending: number }>;
}

interface VisionGoal {
  code: string;
  name: string;
  description: string | null;
  category: string | null;
}

// Sorting types
type SortColumn = "feature_id" | "priority" | "name" | "category" | "last_verified_at" | "criteria" | "verified" | "progress";
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
      const origin = typeof window !== "undefined" ? window.location.origin : "";
      return `${origin}${match[1]}`;
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
      await patch(`${SUMMITFLOW_API}/features/${featureId}/tasks/${taskId}`, {
        completed,
        completedBy: "manual",
      });
      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ["features"] });
    } catch {
      toast.error("Failed to toggle task completion");
    }
  };

  // Fetch features - first get total, then fetch all, then fetch gaps
  const { data: featuresData, isLoading } = useQuery<FeaturesResponse>({
    queryKey: ["features", categoryFilter],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (categoryFilter !== "all") params.set("category", categoryFilter);
      // Note: verification status filtering is done client-side since it's computed dynamically

      // First request to get total count
      params.set("limit", "1");
      const countData = await apiRequest<FeaturesResponse>(`${SUMMITFLOW_API}/features?${params}`);
      const total = countData.total || 200;

      // Fetch all features (max 500 per backend API limit)
      params.set("limit", String(Math.min(total, 500)));
      return apiRequest<FeaturesResponse>(`${SUMMITFLOW_API}/features?${params}`);
    },
  });

  // Fetch summary for counts
  const { data: summaryData } = useQuery<FeaturesSummary>({
    queryKey: ["features-summary"],
    queryFn: () => apiRequest<FeaturesSummary>(`${SUMMITFLOW_API}/features/summary`),
  });

  // Fetch verification summary for criteria status
  const { data: verificationData } = useQuery<VerificationSummary>({
    queryKey: ["verification-summary"],
    queryFn: () => apiRequest<VerificationSummary>(`${SUMMITFLOW_API}/features/verification-summary`),
  });

  // Fetch vision goals for filter dropdown
  const { data: visionGoalsData } = useQuery<VisionGoal[]>({
    queryKey: ["vision-goals"],
    queryFn: () => apiRequest<VisionGoal[]>(`${SUMMITFLOW_API}/vision-goals`),
  });

  // Verify all criteria function
  const handleVerifyAll = async () => {
    setIsVerifying(true);
    try {
      const params = verifyTypeFilter !== "all" ? `?type_filter=${verifyTypeFilter}` : "";
      const data = await post<{ taskId: string }>(`${SUMMITFLOW_API}/features/verify-all${params}`);
      toast.success(`Verification queued: ${data.taskId.slice(0, 8)}...`);
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          await apiRequest<VerificationSummary>(`${SUMMITFLOW_API}/features/verification-summary`);
          queryClient.invalidateQueries({ queryKey: ["verification-summary"] });
        } catch { /* ignore polling errors */ }
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

  // Helper to compute verification status for a feature
  const getVerificationStatus = (f: Feature): "verified" | "needs-review" | "has-tasks" | "no-criteria" => {
    const incompleteTasks = f.totalTasks - f.completedTasks;
    const criteria = f.acceptanceCriteria ?? [];
    const hasCriteria = criteria.length > 0;
    const allPassed = hasCriteria && criteria.every((c) => c.passed === true);

    if (incompleteTasks > 0) return "has-tasks";
    if (!hasCriteria) return "no-criteria";
    if (allPassed) return "verified";
    return "needs-review";
  };

  // Filter features by search query, vision goal, and verification status
  const filteredFeatures = featuresData?.features.filter((f) => {
    // Vision goal filter
    if (visionGoalFilter !== "all") {
      if (!f.visionGoals || !f.visionGoals.includes(visionGoalFilter)) {
        return false;
      }
    }
    // Verification status filter (client-side computed)
    if (passesFilter !== "all") {
      const status = getVerificationStatus(f);
      if (passesFilter === "true" && status !== "verified") return false;
      if (passesFilter === "false" && status !== "needs-review" && status !== "has-tasks") return false;
      if (passesFilter === "null" && status !== "no-criteria") return false;
    }
    // Search filter
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      f.featureId.toLowerCase().includes(q) ||
      f.name.toLowerCase().includes(q) ||
      f.category?.toLowerCase().includes(q) ||
      f.description?.toLowerCase().includes(q)
    );
  }) ?? [];

  // Compute verification status counts using new logic (tasks=0 AND all criteria passed)
  const verificationCounts = useMemo(() => {
    const features = featuresData?.features ?? [];
    let verified = 0;
    let needsReview = 0;
    let hasTasks = 0;
    let noCriteria = 0;

    for (const f of features) {
      const incompleteTasks = f.totalTasks - f.completedTasks;
      const criteria = f.acceptanceCriteria ?? [];
      const hasCriteria = criteria.length > 0;
      const allPassed = hasCriteria && criteria.every((c) => c.passed === true);

      if (incompleteTasks > 0) {
        hasTasks++;
      } else if (!hasCriteria) {
        noCriteria++;
      } else if (allPassed) {
        verified++;
      } else {
        needsReview++;
      }
    }

    return { verified, needsReview, hasTasks, noCriteria };
  }, [featuresData?.features]);

  // Sort features
  const sortedFeatures = [...filteredFeatures].sort((a, b) => {
    let comparison = 0;

    switch (sortColumn) {
      case "feature_id":
        // Natural sort for IDs like FEAT-001, FEAT-002, FEAT-GAP-001
        comparison = a.featureId.localeCompare(b.featureId, undefined, { numeric: true });
        break;
      case "priority":
        comparison = (a.priority ?? a.effectivePriority) - (b.priority ?? b.effectivePriority);
        break;
      case "name":
        comparison = a.name.localeCompare(b.name);
        break;
      case "category":
        comparison = (a.category ?? "").localeCompare(b.category ?? "");
        break;
      case "last_verified_at": {
        const aDate = a.lastVerifiedAt ? new Date(a.lastVerifiedAt).getTime() : 0;
        const bDate = b.lastVerifiedAt ? new Date(b.lastVerifiedAt).getTime() : 0;
        comparison = aDate - bDate;
        break;
      }
      case "criteria": {
        const aPassed = a.acceptanceCriteria?.filter(c => c.passed === true).length ?? 0;
        const bPassed = b.acceptanceCriteria?.filter(c => c.passed === true).length ?? 0;
        const aTotal = a.acceptanceCriteria?.length ?? 0;
        const bTotal = b.acceptanceCriteria?.length ?? 0;
        // Sort by ratio, then by total
        const aRatio = aTotal > 0 ? aPassed / aTotal : 0;
        const bRatio = bTotal > 0 ? bPassed / bTotal : 0;
        comparison = aRatio - bRatio || aTotal - bTotal;
        break;
      }
      case "verified": {
        // Sort by computed verification status: has-tasks=0, no-criteria=1, needs-review=2, verified=3
        const statusOrder = (status: string) => {
          switch(status) {
            case "has-tasks": return 0;
            case "no-criteria": return 1;
            case "needs-review": return 2;
            case "verified": return 3;
            default: return 1;
          }
        };
        comparison = statusOrder(getVerificationStatus(a)) - statusOrder(getVerificationStatus(b));
        break;
      }
      case "progress":
        comparison = a.completionPct - b.completionPct;
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
  const categories = summaryData?.categoryBreakdown
    ? Object.keys(summaryData.categoryBreakdown).sort()
    : [];

  // Category color mapping (deterministic colors per category)
  const categoryColors: Record<string, { bg: string; text: string; border: string }> = {
    "Dashboard": { bg: "#3b82f620", text: "#60a5fa", border: "#3b82f640" },
    "Watchlist": { bg: "#8b5cf620", text: "#a78bfa", border: "#8b5cf640" },
    "Portfolio": { bg: "#06b6d420", text: "#22d3ee", border: "#06b6d440" },
    "Trading": { bg: "#f59e0b20", text: "#fbbf24", border: "#f59e0b40" },
    "Backtest": { bg: "#ec489920", text: "#f472b6", border: "#ec489940" },
    "Strategies": { bg: "#10b98120", text: "#34d399", border: "#10b98140" },
    "Picks": { bg: "#6366f120", text: "#818cf8", border: "#6366f140" },
    "Agents": { bg: "#ef444420", text: "#f87171", border: "#ef444440" },
    "Status": { bg: "#14b8a620", text: "#2dd4bf", border: "#14b8a640" },
    "Settings": { bg: "#78716c20", text: "#a8a29e", border: "#78716c40" },
    "Capabilities": { bg: "#0ea5e920", text: "#38bdf8", border: "#0ea5e940" },
    "Infrastructure": { bg: "#64748b20", text: "#94a3b8", border: "#64748b40" },
  };
  const defaultCategoryColor = { bg: "#71717a20", text: "#a1a1aa", border: "#71717a40" };

  // Get row background color based on verification status
  const getRowBgColor = (feature: Feature) => {
    const status = getVerificationStatus(feature);
    if (status === "verified") return "rgba(34, 197, 94, 0.05)";  // green tint
    if (status === "has-tasks" || status === "needs-review") return "rgba(239, 68, 68, 0.08)"; // red tint
    return "transparent";
  };

  // Render verified status badge
  // Logic: "Verified" only when tasks=0 AND all criteria passed
  const renderPassesBadge = (feature: Feature) => {
    const incompleteTasks = feature.totalTasks - feature.completedTasks;
    const criteria = feature.acceptanceCriteria || [];
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

    const headers = ["Feature ID", "Name", "Category", "Status", "Priority", "Incomplete Tasks", "Criteria Passed", "Total Criteria"];
    const rows = sortedFeatures.map(f => {
      const incompleteTasks = f.totalTasks - f.completedTasks;
      const criteria = f.acceptanceCriteria ?? [];
      const hasCriteria = criteria.length > 0;
      const allPassed = hasCriteria && criteria.every(c => c.passed === true);
      let status = "No Criteria";
      if (incompleteTasks > 0) status = "Has Tasks";
      else if (!hasCriteria) status = "No Criteria";
      else if (allPassed) status = "Verified";
      else status = "Needs Review";
      return [
        f.featureId,
        f.name,
        f.category || "",
        status,
        String(f.priority ?? f.effectivePriority),
        String(incompleteTasks),
        String(criteria.filter(c => c.passed === true).length),
        String(criteria.length),
      ];
    });

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

    const exportData = sortedFeatures.map(f => {
      const incompleteTasks = f.totalTasks - f.completedTasks;
      const criteria = f.acceptanceCriteria ?? [];
      const hasCriteria = criteria.length > 0;
      const allPassed = hasCriteria && criteria.every(c => c.passed === true);
      let status = "no_criteria";
      if (incompleteTasks > 0) status = "has_tasks";
      else if (!hasCriteria) status = "no_criteria";
      else if (allPassed) status = "verified";
      else status = "needs_review";
      return {
        featureId: f.featureId,
        name: f.name,
        category: f.category,
        status,
        priority: f.priority ?? f.effectivePriority,
        incompleteTasks: incompleteTasks,
        criteriaPassed: criteria.filter(c => c.passed === true).length,
        criteriaTotal: criteria.length,
        visionGoals: f.visionGoals,
      };
    });

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
      {/* Summary Cards - Features (using new verification logic) */}
      <div className="grid grid-cols-5 gap-4">
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold">{summaryData?.total || 0}</div>
          <div className="text-sm text-muted-foreground">Total Features</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-green-400">
            {verificationCounts.verified}
          </div>
          <div className="text-sm text-muted-foreground">Verified</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-yellow-400">
            {verificationCounts.needsReview}
          </div>
          <div className="text-sm text-muted-foreground">Needs Review</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-orange-400">
            {verificationCounts.hasTasks}
          </div>
          <div className="text-sm text-muted-foreground">Has Tasks</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-zinc-400">
            {verificationCounts.noCriteria}
          </div>
          <div className="text-sm text-muted-foreground">No Criteria</div>
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
              <span className="text-xs text-muted-foreground">{verificationData.totalCriteria} total</span>
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
          {verificationData.byType && Object.keys(verificationData.byType).length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/50 flex gap-4 text-xs">
              {Object.entries(verificationData.byType).map(([type, stats]) => (
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
                  onClick={() => handleSort("verified")}
                >
                  <div className="flex items-center">
                    Verified{getSortIcon("verified")}
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
                const isExpanded = expandedRows.has(feature.featureId);
                const hasTasks = feature.tasks && feature.tasks.length > 0;

                return (
                  <Fragment key={feature.featureId}>
                    <TableRow
                      className={(hasTasks || (feature.acceptanceCriteria && feature.acceptanceCriteria.length > 0)) ? "cursor-pointer hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-accent" : ""}
                      onClick={() => (hasTasks || (feature.acceptanceCriteria && feature.acceptanceCriteria.length > 0)) && toggleRow(feature.featureId)}
                      onKeyDown={(e) => {
                        if ((e.key === "Enter" || e.key === " ") && (hasTasks || (feature.acceptanceCriteria && feature.acceptanceCriteria.length > 0))) {
                          e.preventDefault();
                          toggleRow(feature.featureId);
                        }
                      }}
                      tabIndex={(hasTasks || (feature.acceptanceCriteria && feature.acceptanceCriteria.length > 0)) ? 0 : -1}
                      role="row"
                      aria-expanded={(hasTasks || (feature.acceptanceCriteria && feature.acceptanceCriteria.length > 0)) ? isExpanded : undefined}
                      style={{ backgroundColor: getRowBgColor(feature) }}
                    >
                      <TableCell className="font-mono text-xs px-2 align-top py-2 w-20">
                        <div className="flex items-center gap-1">
                          <span
                            className="w-4 h-4 inline-flex items-center justify-center shrink-0"
                            aria-hidden="true"
                          >
                            {(hasTasks || (feature.acceptanceCriteria && feature.acceptanceCriteria.length > 0)) && (
                              isExpanded ? (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                              )
                            )}
                          </span>
                          <span
                            style={{
                              color: getVerificationStatus(feature) === "verified"
                                ? "#4ade80"  // green-400
                                : getVerificationStatus(feature) === "has-tasks" || getVerificationStatus(feature) === "needs-review"
                                ? "#f87171"  // red-400
                                : "#a1a1aa", // zinc-400 for no-criteria
                            }}
                          >
                            <HighlightMatch text={feature.featureId} query={searchQuery} />
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-10 text-center">
                        {renderPriorityBadge(feature.priority, feature.effectivePriority)}
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-40">
                        <div className="flex items-center gap-1">
                          {getVerificationStatus(feature) === "needs-review" && (
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
                          title={feature.lastVerifiedAt ? new Date(feature.lastVerifiedAt).toLocaleString() : "Never verified"}
                        >
                          {formatRelativeTime(feature.lastVerifiedAt)}
                        </span>
                      </TableCell>
                      <TableCell className="px-2 text-center align-top py-2 w-14">
                        {renderCriteriaStatus(feature.acceptanceCriteria)}
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-24">{renderPassesBadge(feature)}</TableCell>
                      <TableCell className="px-2 text-right align-top py-2 w-20">
                        {(() => {
                          const incompleteTasks = feature.totalTasks - feature.completedTasks;
                          return (
                            <span
                              className="text-xs font-mono"
                              style={{
                                color: incompleteTasks === 0
                                  ? "#4ade80"  // green-400 (no tasks)
                                  : "#facc15", // yellow-400 (has tasks)
                              }}
                              title={`${feature.completedTasks}/${feature.totalTasks} completed`}
                            >
                              {incompleteTasks}
                            </span>
                          );
                        })()}
                      </TableCell>
                    </TableRow>
                    {/* Expanded details row (subtasks + acceptance criteria) */}
                    {isExpanded && (hasTasks || (feature.acceptanceCriteria && feature.acceptanceCriteria.length > 0)) && (
                      <TableRow key={`${feature.featureId}-details`} className="bg-muted/30">
                        <TableCell colSpan={8} className="py-2 px-4">
                          <div className="pl-6 space-y-4">
                            {/* Acceptance Criteria Section */}
                            {feature.acceptanceCriteria && feature.acceptanceCriteria.length > 0 && (
                              <div className="space-y-1">
                                <div className="flex items-center justify-between mb-3">
                                  <span className="text-xs font-medium text-muted-foreground">
                                    Acceptance Criteria ({feature.acceptanceCriteria.filter(c => c.passed === true).length}/{feature.acceptanceCriteria.length} verified)
                                  </span>
                                  <span className="text-[10px] text-muted-foreground/70 flex items-center gap-3">
                                    <span className="flex items-center gap-0.5"><CheckCircle2 className="h-3 w-3 text-green-400" />pass</span>
                                    <span className="flex items-center gap-0.5"><XCircle className="h-3 w-3 text-red-400" />fail</span>
                                    <span className="flex items-center gap-0.5"><HelpCircle className="h-3 w-3 text-yellow-500" />pending</span>
                                  </span>
                                </div>
                                {feature.acceptanceCriteria.map((criterion) => (
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
                                              featureId: feature.featureId,
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
                            {feature.visionGoals && feature.visionGoals.length > 0 && (
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">Vision Goals:</span>
                                <TooltipProvider>
                                  {feature.visionGoals.map((goalCode) => {
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
                            {feature.implementationNotes && Object.keys(feature.implementationNotes).length > 0 && (
                              <div className="space-y-2 border-t border-border/50 pt-3">
                                <div className="flex items-center gap-2 mb-2">
                                  <BookOpen className="h-4 w-4 text-blue-400" />
                                  <span className="text-xs font-medium text-muted-foreground">Implementation Notes</span>
                                </div>
                                {/* Context */}
                                {feature.implementationNotes.context && (
                                  <div className="bg-muted/30 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Context</span>
                                    <p className="text-sm mt-1">{feature.implementationNotes.context}</p>
                                  </div>
                                )}
                                {/* Steps */}
                                {feature.implementationNotes.steps && feature.implementationNotes.steps.length > 0 && (
                                  <div className="bg-muted/30 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Steps</span>
                                    <ol className="list-decimal list-inside text-sm mt-1 space-y-0.5">
                                      {feature.implementationNotes.steps.map((step, idx) => (
                                        <li key={idx} className="text-sm">{step}</li>
                                      ))}
                                    </ol>
                                  </div>
                                )}
                                {/* Files */}
                                {feature.implementationNotes.files && feature.implementationNotes.files.length > 0 && (
                                  <div className="bg-muted/30 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground flex items-center gap-1">
                                      <Code className="h-3 w-3" /> Files to Modify
                                    </span>
                                    <div className="flex flex-wrap gap-1 mt-1">
                                      {feature.implementationNotes.files.map((file, idx) => (
                                        <code key={idx} className="text-xs bg-surface px-1.5 py-0.5 rounded font-mono text-blue-400">
                                          {file}
                                        </code>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {/* Blockers */}
                                {feature.implementationNotes.blockers && feature.implementationNotes.blockers.length > 0 && (
                                  <div className="bg-red-500/10 border border-red-500/20 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-red-400 flex items-center gap-1">
                                      <AlertTriangle className="h-3 w-3" /> Blockers
                                    </span>
                                    <ul className="list-disc list-inside text-sm mt-1 text-red-400">
                                      {feature.implementationNotes.blockers.map((blocker, idx) => (
                                        <li key={idx}>{blocker}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                {/* Notes */}
                                {feature.implementationNotes.notes && (
                                  <div className="bg-muted/30 rounded p-2">
                                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Notes</span>
                                    <p className="text-sm mt-1 whitespace-pre-wrap">{feature.implementationNotes.notes}</p>
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
                                  Subtasks ({feature.completedTasks}/{feature.totalTasks})
                                </div>
                                {feature.tasks.map((task) => (
                                  <div
                                    key={task.taskId}
                                    className="bg-muted/20 rounded p-2 space-y-1"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <div className="flex items-center gap-2">
                                      <Checkbox
                                        checked={task.completed}
                                        onCheckedChange={(checked) =>
                                          toggleTask(feature.featureId, task.taskId, checked as boolean)
                                        }
                                        className="shrink-0"
                                      />
                                      <span className="font-mono text-xs text-muted-foreground shrink-0 min-w-[50px]">
                                        {task.taskId}
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
                                      {task.taskType && task.taskType !== "implementation" && (
                                        <span
                                          className="text-[10px] px-1 py-0.5 rounded border shrink-0"
                                          style={{
                                            backgroundColor: task.taskType === "fix" ? "#ef444420" : task.taskType === "task_file" ? "#a855f720" : task.taskType === "discovery" ? "#f9731620" : "#71717a20",
                                            color: task.taskType === "fix" ? "#f87171" : task.taskType === "task_file" ? "#c084fc" : task.taskType === "discovery" ? "#fb923c" : "#a1a1aa",
                                            borderColor: task.taskType === "fix" ? "#ef444440" : task.taskType === "task_file" ? "#a855f740" : task.taskType === "discovery" ? "#f9731640" : "#71717a40",
                                          }}
                                        >
                                          {task.taskType}
                                        </span>
                                      )}
                                      <span className={`flex-1 ${task.completed ? "line-through text-muted-foreground" : ""}`}>
                                        {task.description}
                                      </span>
                                      {task.completedBy && (
                                        <span className="text-xs text-muted-foreground shrink-0">
                                          by {task.completedBy}
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
