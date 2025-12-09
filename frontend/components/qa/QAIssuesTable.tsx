"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { CheckCircle2, XCircle, AlertTriangle, Code } from "lucide-react";
import {
  QAIssue,
  QASeverity,
  QACategory,
  resolveQAIssue,
  markFalsePositive,
} from "@/lib/api/qa";

interface QAIssuesTableProps {
  issues: QAIssue[];
  isLoading?: boolean;
}

/**
 * Get severity badge color
 */
function getSeverityColor(severity: QASeverity): {
  bg: string;
  text: string;
  border: string;
  icon: React.ReactNode;
} {
  switch (severity) {
    case "critical":
      return {
        bg: "#ef444420",
        text: "#f87171",
        border: "#ef444440",
        icon: <XCircle className="h-3 w-3" />,
      };
    case "high":
      return {
        bg: "#f9731620",
        text: "#fb923c",
        border: "#f9731640",
        icon: <AlertTriangle className="h-3 w-3" />,
      };
    case "medium":
      return {
        bg: "#eab30820",
        text: "#facc15",
        border: "#eab30840",
        icon: <AlertTriangle className="h-3 w-3" />,
      };
    case "low":
      return {
        bg: "#3b82f620",
        text: "#60a5fa",
        border: "#3b82f640",
        icon: <AlertTriangle className="h-3 w-3" />,
      };
  }
}

/**
 * Get category badge color
 */
function getCategoryColor(category: QACategory): {
  bg: string;
  text: string;
  border: string;
} {
  const colors: Record<QACategory, { bg: string; text: string; border: string }> = {
    style: { bg: "#8b5cf620", text: "#a78bfa", border: "#8b5cf640" },
    type: { bg: "#3b82f620", text: "#60a5fa", border: "#3b82f640" },
    performance: { bg: "#f9731620", text: "#fb923c", border: "#f9731640" },
    security: { bg: "#ef444420", text: "#f87171", border: "#ef444440" },
    reliability: { bg: "#eab30820", text: "#facc15", border: "#eab30840" },
    maintainability: { bg: "#10b98120", text: "#34d399", border: "#10b98140" },
    "api-contract": { bg: "#06b6d420", text: "#22d3ee", border: "#06b6d440" },
    "data-quality": { bg: "#6366f120", text: "#818cf8", border: "#6366f140" },
    "test-coverage": { bg: "#ec489920", text: "#f472b6", border: "#ec489940" },
  };
  return colors[category] || { bg: "#71717a20", text: "#a1a1aa", border: "#71717a40" };
}

/**
 * Format relative time
 */
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return "now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return `${Math.floor(diffDays / 30)}mo ago`;
}

export function QAIssuesTable({ issues, isLoading }: QAIssuesTableProps) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [resolveNotes, setResolveNotes] = useState<Record<string, string>>({});
  const queryClient = useQueryClient();

  // Resolve issue mutation
  const resolveMutation = useMutation({
    mutationFn: ({ issueId, notes }: { issueId: string; notes?: string }) =>
      resolveQAIssue(issueId, { resolved_by: "manual", notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["qa-issues"] });
      queryClient.invalidateQueries({ queryKey: ["qa-summary"] });
      toast.success("Issue marked as resolved");
    },
    onError: () => {
      toast.error("Failed to resolve issue");
    },
  });

  // False positive mutation
  const falsePositiveMutation = useMutation({
    mutationFn: ({ issueId, notes }: { issueId: string; notes?: string }) =>
      markFalsePositive(issueId, { notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["qa-issues"] });
      queryClient.invalidateQueries({ queryKey: ["qa-summary"] });
      toast.success("Issue marked as false positive");
    },
    onError: () => {
      toast.error("Failed to mark as false positive");
    },
  });

  const handleResolve = (issueId: string) => {
    resolveMutation.mutate({ issueId, notes: resolveNotes[issueId] });
    setResolveNotes((prev) => ({ ...prev, [issueId]: "" }));
    setExpandedRow(null);
  };

  const handleFalsePositive = (issueId: string) => {
    falsePositiveMutation.mutate({ issueId, notes: resolveNotes[issueId] });
    setResolveNotes((prev) => ({ ...prev, [issueId]: "" }));
    setExpandedRow(null);
  };

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border">
        <div className="p-8 text-center text-muted-foreground">Loading issues...</div>
      </div>
    );
  }

  if (issues.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-green-400 opacity-50" />
        <p className="mt-4 text-sm text-muted-foreground">
          No QA issues found. Great job!
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-24">ID</TableHead>
            <TableHead className="w-32">Category</TableHead>
            <TableHead className="w-24">Severity</TableHead>
            <TableHead className="w-64">File Path</TableHead>
            <TableHead>Description</TableHead>
            <TableHead className="w-24">Detected</TableHead>
            <TableHead className="w-24">Status</TableHead>
            <TableHead className="w-32">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {issues.map((issue) => {
            const isExpanded = expandedRow === issue.id;
            const severityColor = getSeverityColor(issue.severity);
            const categoryColor = getCategoryColor(issue.category);
            const isResolved = issue.resolved_at !== null;
            const isFalsePositive = issue.is_false_positive;

            return (
              <TableRow
                key={issue.id}
                className={isResolved ? "opacity-60" : ""}
                style={{
                  backgroundColor: isResolved
                    ? "rgba(34, 197, 94, 0.05)"
                    : isFalsePositive
                    ? "rgba(113, 113, 122, 0.05)"
                    : "transparent",
                }}
              >
                <TableCell className="font-mono text-xs align-top py-2">
                  {issue.issue_id}
                </TableCell>
                <TableCell className="align-top py-2">
                  <span
                    className="text-xs px-2 py-1 rounded border"
                    style={{
                      backgroundColor: categoryColor.bg,
                      color: categoryColor.text,
                      borderColor: categoryColor.border,
                    }}
                  >
                    {issue.category}
                  </span>
                </TableCell>
                <TableCell className="align-top py-2">
                  <span
                    className="text-xs px-2 py-1 rounded border inline-flex items-center gap-1"
                    style={{
                      backgroundColor: severityColor.bg,
                      color: severityColor.text,
                      borderColor: severityColor.border,
                    }}
                  >
                    {severityColor.icon}
                    {issue.severity}
                  </span>
                </TableCell>
                <TableCell className="align-top py-2">
                  <div className="flex items-start gap-1">
                    <Code className="h-3 w-3 text-muted-foreground mt-0.5 shrink-0" />
                    <span className="text-xs font-mono text-blue-400 break-all">
                      {issue.file_path}
                      {issue.line_number && `:${issue.line_number}`}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="align-top py-2">
                  <div className="space-y-1">
                    <p className="text-sm">{issue.description}</p>
                    {issue.suggestion && (
                      <p className="text-xs text-muted-foreground">
                        <span className="text-muted-foreground/60">Suggestion: </span>
                        {issue.suggestion}
                      </p>
                    )}
                    {isExpanded && (
                      <div className="mt-3 space-y-2">
                        <Textarea
                          placeholder="Optional notes..."
                          value={resolveNotes[issue.id] || ""}
                          onChange={(e) =>
                            setResolveNotes((prev) => ({ ...prev, [issue.id]: e.target.value }))
                          }
                          className="text-xs h-16"
                        />
                      </div>
                    )}
                  </div>
                </TableCell>
                <TableCell className="align-top py-2">
                  <span className="text-xs text-muted-foreground">
                    {formatRelativeTime(issue.detected_at)}
                  </span>
                </TableCell>
                <TableCell className="align-top py-2">
                  {isResolved ? (
                    <Badge
                      variant="default"
                      className="bg-green-500/20 text-green-400 border-green-500/30"
                    >
                      <CheckCircle2 className="mr-1 h-3 w-3" />
                      Resolved
                    </Badge>
                  ) : isFalsePositive ? (
                    <Badge
                      variant="default"
                      className="bg-gray-500/20 text-gray-400 border-gray-500/30"
                    >
                      False Positive
                    </Badge>
                  ) : (
                    <Badge
                      variant="default"
                      className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
                    >
                      Open
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="align-top py-2">
                  {!isResolved && !isFalsePositive && (
                    <div className="flex flex-col gap-1">
                      {isExpanded ? (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleResolve(issue.id)}
                            disabled={resolveMutation.isPending}
                            className="h-6 text-xs"
                          >
                            <CheckCircle2 className="h-3 w-3 mr-1" />
                            Confirm
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleFalsePositive(issue.id)}
                            disabled={falsePositiveMutation.isPending}
                            className="h-6 text-xs"
                          >
                            <XCircle className="h-3 w-3 mr-1" />
                            False +
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setExpandedRow(null)}
                            className="h-6 text-xs"
                          >
                            Cancel
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setExpandedRow(issue.id)}
                          className="h-6 text-xs"
                        >
                          Resolve
                        </Button>
                      )}
                    </div>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
