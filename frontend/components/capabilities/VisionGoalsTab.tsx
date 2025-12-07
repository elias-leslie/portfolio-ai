"use client";

import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  ChevronDown,
  ChevronRight,
  Target,
  Loader2,
  CheckCircle2,
  XCircle,
  HelpCircle,
} from "lucide-react";

interface VisionGoal {
  code: string;
  name: string;
  description: string | null;
  category: string | null;
  feature_count: number;
  criteria_total: number;
  criteria_passed: number;
  pass_rate: number;
}

interface FeatureLink {
  feature_id: string;
  name: string;
  passes: boolean | null;
  criteria_total: number;
  criteria_passed: number;
}

interface VisionGoalDetail extends VisionGoal {
  features: FeatureLink[];
}

export function VisionGoalsTab() {
  const [expandedGoals, setExpandedGoals] = useState<Set<string>>(new Set());

  // Fetch all vision goals
  const { data: goalsData, isLoading } = useQuery<VisionGoal[]>({
    queryKey: ["vision-goals"],
    queryFn: async () => {
      const response = await fetch("/api/vision-goals");
      if (!response.ok) throw new Error("Failed to fetch vision goals");
      return response.json();
    },
  });

  // Toggle goal expansion
  const toggleGoal = (code: string) => {
    setExpandedGoals((prev) => {
      const next = new Set(prev);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      return next;
    });
  };

  // Category color mapping
  const categoryColors: Record<string, { bg: string; text: string; border: string }> = {
    "Intelligence": { bg: "#3b82f620", text: "#60a5fa", border: "#3b82f640" },
    "Automation": { bg: "#8b5cf620", text: "#a78bfa", border: "#8b5cf640" },
    "Experience": { bg: "#06b6d420", text: "#22d3ee", border: "#06b6d440" },
    "Reliability": { bg: "#10b98120", text: "#34d399", border: "#10b98140" },
    "Transparency": { bg: "#f59e0b20", text: "#fbbf24", border: "#f59e0b40" },
    "Adaptability": { bg: "#ec489920", text: "#f472b6", border: "#ec489940" },
    "Integration": { bg: "#6366f120", text: "#818cf8", border: "#6366f140" },
  };
  const defaultColor = { bg: "#71717a20", text: "#a1a1aa", border: "#71717a40" };

  // Get pass rate color
  const getPassRateColor = (rate: number) => {
    if (rate >= 0.8) return "#4ade80"; // green
    if (rate >= 0.5) return "#facc15"; // yellow
    if (rate > 0) return "#f97316"; // orange
    return "#71717a"; // gray
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const goals = goalsData || [];

  // Calculate totals
  const totalFeatures = goals.reduce((sum, g) => sum + g.feature_count, 0);
  const totalCriteria = goals.reduce((sum, g) => sum + g.criteria_total, 0);
  const totalPassed = goals.reduce((sum, g) => sum + g.criteria_passed, 0);
  const overallPassRate = totalCriteria > 0 ? totalPassed / totalCriteria : 0;

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold">{goals.length}</div>
          <div className="text-sm text-muted-foreground">Vision Goals</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold">{totalFeatures}</div>
          <div className="text-sm text-muted-foreground">Linked Features</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold">{totalCriteria}</div>
          <div className="text-sm text-muted-foreground">Acceptance Criteria</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div
            className="text-2xl font-bold"
            style={{ color: getPassRateColor(overallPassRate) }}
          >
            {Math.round(overallPassRate * 100)}%
          </div>
          <div className="text-sm text-muted-foreground">Overall Pass Rate</div>
        </div>
      </div>

      {/* Vision Goals Table */}
      {goals.length > 0 ? (
        <div className="rounded-lg border border-border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="px-2 w-28">Code</TableHead>
                <TableHead className="px-2 w-48">Name</TableHead>
                <TableHead className="px-2 w-28">Category</TableHead>
                <TableHead className="px-2 w-24 text-center">Features</TableHead>
                <TableHead className="px-2 w-24 text-center">Criteria</TableHead>
                <TableHead className="px-2 w-36">Pass Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {goals.map((goal) => {
                const isExpanded = expandedGoals.has(goal.code);
                const colors = goal.category
                  ? categoryColors[goal.category] || defaultColor
                  : defaultColor;

                return (
                  <Fragment key={goal.code}>
                    <TableRow
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => toggleGoal(goal.code)}
                    >
                      <TableCell className="px-2 py-2">
                        <div className="flex items-center gap-1">
                          <span className="w-4 h-4 inline-flex items-center justify-center shrink-0">
                            {isExpanded ? (
                              <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            )}
                          </span>
                          <span className="font-mono text-xs text-purple-400">
                            {goal.code}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="px-2 py-2">
                        <div className="flex items-center gap-2">
                          <Target className="h-4 w-4 text-muted-foreground shrink-0" />
                          <span className="font-medium">{goal.name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="px-2 py-2">
                        {goal.category && (
                          <span
                            className="text-xs px-1.5 py-0.5 rounded border"
                            style={{
                              backgroundColor: colors.bg,
                              color: colors.text,
                              borderColor: colors.border,
                            }}
                          >
                            {goal.category}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="px-2 py-2 text-center">
                        <span className="text-sm">{goal.feature_count}</span>
                      </TableCell>
                      <TableCell className="px-2 py-2 text-center">
                        <span
                          className="text-sm font-mono"
                          style={{
                            color:
                              goal.criteria_passed === goal.criteria_total &&
                              goal.criteria_total > 0
                                ? "#4ade80"
                                : "#a1a1aa",
                          }}
                        >
                          {goal.criteria_passed}/{goal.criteria_total}
                        </span>
                      </TableCell>
                      <TableCell className="px-2 py-2">
                        <div className="flex items-center gap-2">
                          <Progress
                            value={goal.pass_rate * 100}
                            className="h-2 w-20"
                          />
                          <span
                            className="text-xs font-medium"
                            style={{ color: getPassRateColor(goal.pass_rate) }}
                          >
                            {Math.round(goal.pass_rate * 100)}%
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                    {/* Expanded row showing linked features */}
                    {isExpanded && (
                      <TableRow className="bg-muted/30">
                        <TableCell colSpan={6} className="py-3 px-4">
                          <ExpandedGoalFeatures code={goal.code} />
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
          <Target className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
          <p className="mt-4 text-sm text-muted-foreground">
            No vision goals found. Run migration 083 to populate goals from VISION.md.
          </p>
        </div>
      )}
    </div>
  );
}

// Sub-component to fetch and display linked features
function ExpandedGoalFeatures({ code }: { code: string }) {
  const { data, isLoading } = useQuery<VisionGoalDetail>({
    queryKey: ["vision-goal", code],
    queryFn: async () => {
      const response = await fetch(`/api/vision-goals/${code}`);
      if (!response.ok) throw new Error("Failed to fetch goal details");
      return response.json();
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading features...
      </div>
    );
  }

  const features = data?.features || [];

  if (features.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        No features linked to this vision goal.
      </div>
    );
  }

  return (
    <div className="pl-6 space-y-2">
      <div className="text-xs font-medium text-muted-foreground mb-2">
        Linked Features ({features.length})
      </div>
      <div className="grid grid-cols-2 gap-2">
        {features.map((f) => (
          <div
            key={f.feature_id}
            className="flex items-center gap-2 text-sm py-1 px-2 rounded bg-muted/30"
          >
            {f.passes === true ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0" />
            ) : f.passes === false ? (
              <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
            ) : (
              <HelpCircle className="h-3.5 w-3.5 text-yellow-500 shrink-0" />
            )}
            <span className="font-mono text-xs text-muted-foreground shrink-0">
              {f.feature_id}
            </span>
            <span className="truncate flex-1">{f.name}</span>
            {f.criteria_total > 0 && (
              <span
                className="text-xs font-mono shrink-0"
                style={{
                  color:
                    f.criteria_passed === f.criteria_total
                      ? "#4ade80"
                      : f.criteria_passed > 0
                      ? "#facc15"
                      : "#71717a",
                }}
              >
                {f.criteria_passed}/{f.criteria_total}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
