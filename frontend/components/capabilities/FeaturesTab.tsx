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
  Play,
  Target,
  Eye,
  BookOpen,
  Code,
  AlertTriangle,
} from "lucide-react";
import { EvidenceViewerModal } from "./EvidenceViewerModal";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

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

interface GapLink {
  gap_id: string;
  relationship_type: string;
  linked_by: string;
  linked_at: string;
}

export function FeaturesTab() {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [passesFilter, setPassesFilter] = useState("all");
  const [visionGoalFilter, setVisionGoalFilter] = useState("all");
  const [gapFilter, setGapFilter] = useState("all");
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [featureGaps, setFeatureGaps] = useState<Record<string, GapLink[]>>({});
  const [pageSize, setPageSize] = useState(25);
  const [currentPage, setCurrentPage] = useState(1);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyTypeFilter, setVerifyTypeFilter] = useState("api");
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

  // Fetch gaps for a feature
  const fetchFeatureGaps = async (featureId: string) => {
    try {
      const response = await fetch(`/api/capabilities/features/${featureId}/gaps`);
      if (response.ok) {
        const gaps = await response.json();
        setFeatureGaps((prev) => ({ ...prev, [featureId]: gaps }));
      }
    } catch {
      // Silently fail - gaps are optional
    }
  };

  // Toggle row expansion
  const toggleRow = async (featureId: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(featureId)) {
        next.delete(featureId);
      } else {
        next.add(featureId);
        // Fetch gaps when expanding if not already loaded
        if (!featureGaps[featureId]) {
          fetchFeatureGaps(featureId);
        }
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

      // Fetch all features (up to 1000 max for safety)
      params.set("limit", String(Math.min(total, 1000)));
      const response = await fetch(`/api/capabilities/features/?${params}`);
      if (!response.ok) throw new Error("Failed to fetch features");
      const data = await response.json();

      // Pre-fetch gaps for all features to enable filtering
      if (data.features && data.features.length > 0) {
        const gapsPromises = data.features.map((f: Feature) =>
          fetch(`/api/capabilities/features/${f.feature_id}/gaps`)
            .then((r) => r.ok ? r.json() : [])
            .then((gaps) => ({ featureId: f.feature_id, gaps }))
            .catch(() => ({ featureId: f.feature_id, gaps: [] }))
        );
        const gapsResults = await Promise.all(gapsPromises);
        const gapsMap: Record<string, GapLink[]> = {};
        gapsResults.forEach(({ featureId, gaps }) => {
          gapsMap[featureId] = gaps;
        });
        setFeatureGaps(gapsMap);
      }

      return data;
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

  // Filter features by search query, vision goal, and gap
  const filteredFeatures = featuresData?.features.filter((f) => {
    // Vision goal filter
    if (visionGoalFilter !== "all") {
      if (!f.vision_goals || !f.vision_goals.includes(visionGoalFilter)) {
        return false;
      }
    }
    // Gap filter
    if (gapFilter !== "all") {
      const gaps = featureGaps[f.feature_id];
      if (!gaps || !gaps.some((g) => g.gap_id === gapFilter)) {
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

  // Render status badge
  const renderStatusBadge = (status: string) => {
    const colors: Record<string, { bg: string; text: string; border: string }> = {
      pending: { bg: "#71717a20", text: "#a1a1aa", border: "#71717a40" },
      in_progress: { bg: "#3b82f620", text: "#60a5fa", border: "#3b82f640" },
      review_needed: { bg: "#eab30820", text: "#facc15", border: "#eab30840" },
      deferred: { bg: "#8b5cf620", text: "#a78bfa", border: "#8b5cf640" },
      blocked: { bg: "#ef444420", text: "#f87171", border: "#ef444440" },
      complete: { bg: "#22c55e20", text: "#4ade80", border: "#22c55e40" },
    };
    const color = colors[status] || colors.pending;
    const labels: Record<string, string> = {
      pending: "Pending",
      in_progress: "In Progress",
      review_needed: "Review",
      deferred: "Deferred",
      blocked: "Blocked",
      complete: "Complete",
    };
    return (
      <span
        className="text-[10px] px-1.5 py-0.5 rounded border"
        style={{ backgroundColor: color.bg, color: color.text, borderColor: color.border }}
      >
        {labels[status] || status}
      </span>
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

        {/* Gap filter - shows gaps that are linked to features */}
        {Object.values(featureGaps).flat().length > 0 && (
          <Select value={gapFilter} onValueChange={(v) => { setGapFilter(v); setCurrentPage(1); }}>
            <SelectTrigger className="w-[140px]">
              <AlertTriangle className="mr-2 h-4 w-4" />
              <SelectValue placeholder="Gap" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Gaps</SelectItem>
              {Array.from(new Set(Object.values(featureGaps).flat().map(g => g.gap_id))).sort().map((gapId) => (
                <SelectItem key={gapId} value={gapId}>
                  {gapId}
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
                <TableHead className="px-2 w-10 text-center">P</TableHead>
                <TableHead className="px-2 w-8 text-center">E</TableHead>
                <TableHead className="px-2 w-40">Name</TableHead>
                <TableHead className="px-2 w-24">Category</TableHead>
                <TableHead className="px-2 w-20">Gaps</TableHead>
                <TableHead className="px-2 w-20">Work</TableHead>
                <TableHead className="px-2 w-14 text-center">Criteria</TableHead>
                <TableHead className="px-2 w-24">Verified</TableHead>
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
                      className={(hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0)) ? "cursor-pointer hover:bg-muted/50" : ""}
                      onClick={() => (hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0)) && toggleRow(feature.feature_id)}
                      style={{ backgroundColor: getRowBgColor(feature.passes) }}
                    >
                      <TableCell className="font-mono text-xs px-2 align-top py-2 w-20">
                        <div className="flex items-center gap-1">
                          <span className="w-4 h-4 inline-flex items-center justify-center shrink-0">
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
                            {feature.feature_id}
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
                            />
                          )}
                          <span className="font-medium truncate" title={feature.name}>
                            {feature.name}
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
                      <TableCell className="px-2 align-top py-2 w-20">
                        {featureGaps[feature.feature_id] && featureGaps[feature.feature_id].length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {featureGaps[feature.feature_id].slice(0, 2).map((gap) => (
                              <Badge key={gap.gap_id} variant="outline" className="text-[10px] px-1 py-0">
                                {gap.gap_id}
                              </Badge>
                            ))}
                            {featureGaps[feature.feature_id].length > 2 && (
                              <span className="text-[10px] text-muted-foreground">
                                +{featureGaps[feature.feature_id].length - 2}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="px-2 align-top py-2 w-20">
                        {renderStatusBadge(feature.status)}
                      </TableCell>
                      <TableCell className="px-2 text-center align-top py-2 w-14">
                        {renderCriteriaStatus(feature.acceptance_criteria)}
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
                    {/* Expanded details row (subtasks + acceptance criteria) */}
                    {isExpanded && (hasTasks || (feature.acceptance_criteria && feature.acceptance_criteria.length > 0)) && (
                      <TableRow key={`${feature.feature_id}-details`} className="bg-muted/30">
                        <TableCell colSpan={10} className="py-2 px-4">
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
