"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  RefreshCw,
  Loader2,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { QAIssuesTable } from "./QAIssuesTable";
import { QATrendChart } from "./QATrendChart";
import {
  fetchQASummary,
  fetchQAIssues,
  fetchQATrends,
  triggerQAScan,
  QACategory,
  QASeverity,
  QASummary,
  QAIssuesResponse,
  QATrendsResponse,
} from "@/lib/api/qa";

export function QATab() {
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [resolvedFilter, setResolvedFilter] = useState<string>("false");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  const queryClient = useQueryClient();

  // Fetch QA summary
  const { data: summaryData, isLoading: summaryLoading } = useQuery<QASummary>({
    queryKey: ["qa-summary"],
    queryFn: fetchQASummary,
  });

  // Fetch QA issues
  const { data: issuesData, isLoading: issuesLoading } = useQuery<QAIssuesResponse>({
    queryKey: [
      "qa-issues",
      categoryFilter,
      severityFilter,
      resolvedFilter,
      currentPage,
      pageSize,
    ],
    queryFn: () =>
      fetchQAIssues({
        category: categoryFilter !== "all" ? (categoryFilter as QACategory) : undefined,
        severity: severityFilter !== "all" ? (severityFilter as QASeverity) : undefined,
        resolved: resolvedFilter === "all" ? undefined : resolvedFilter === "true",
        limit: pageSize,
        offset: (currentPage - 1) * pageSize,
      }),
  });

  // Fetch QA trends
  const { data: trendsData, isLoading: trendsLoading } = useQuery<QATrendsResponse>({
    queryKey: ["qa-trends"],
    queryFn: () => fetchQATrends(30),
  });

  // Scan mutation
  const scanMutation = useMutation({
    mutationFn: triggerQAScan,
    onSuccess: (data) => {
      toast.success(`QA scan started: ${data.task_id.slice(0, 8)}...`);
      // Poll for completion
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["qa-summary"] });
        queryClient.invalidateQueries({ queryKey: ["qa-issues"] });
        queryClient.invalidateQueries({ queryKey: ["qa-trends"] });
        toast.success("QA scan complete. Refreshing data...");
      }, 10000);
    },
    onError: () => {
      toast.error("Failed to start QA scan");
    },
  });

  const handleScanNow = () => {
    scanMutation.mutate();
  };

  // Calculate trend indicator for resolved this week
  const resolutionTrend = summaryData
    ? summaryData.resolved_this_week > summaryData.added_this_week
      ? "up"
      : summaryData.resolved_this_week < summaryData.added_this_week
      ? "down"
      : "neutral"
    : "neutral";

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Issues
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {summaryLoading ? (
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              ) : (
                summaryData?.total_issues || 0
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Critical
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-red-400">
              {summaryLoading ? (
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              ) : (
                summaryData?.critical_count || 0
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Resolved This Week
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className="text-3xl font-bold text-green-400">
                {summaryLoading ? (
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                ) : (
                  summaryData?.resolved_this_week || 0
                )}
              </div>
              {!summaryLoading && resolutionTrend === "up" && (
                <TrendingUp className="h-5 w-5 text-green-400" />
              )}
              {!summaryLoading && resolutionTrend === "down" && (
                <TrendingDown className="h-5 w-5 text-red-400" />
              )}
              {!summaryLoading && resolutionTrend === "neutral" && (
                <Minus className="h-5 w-5 text-yellow-400" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Added This Week
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-yellow-400">
              {summaryLoading ? (
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              ) : (
                summaryData?.added_this_week || 0
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Severity Breakdown */}
      {summaryData && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Severity Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <span className="text-muted-foreground">Critical:</span>
                <span className="font-semibold">{summaryData.critical_count}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-orange-500" />
                <span className="text-muted-foreground">High:</span>
                <span className="font-semibold">{summaryData.high_count}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <span className="text-muted-foreground">Medium:</span>
                <span className="font-semibold">{summaryData.medium_count}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500" />
                <span className="text-muted-foreground">Low:</span>
                <span className="font-semibold">{summaryData.low_count}</span>
              </div>
              {summaryData.resolution_rate !== undefined && (
                <div className="flex items-center gap-2 ml-auto">
                  <CheckCircle className="h-4 w-4 text-green-400" />
                  <span className="text-muted-foreground">Resolution Rate:</span>
                  <span className="font-semibold text-green-400">
                    {(summaryData.resolution_rate * 100).toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Trend Chart */}
      <QATrendChart trends={trendsData?.trends || []} isLoading={trendsLoading} />

      {/* Filters and Scan Button */}
      <div className="flex flex-wrap gap-3 items-center">
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            <SelectItem value="style">Style</SelectItem>
            <SelectItem value="type">Type</SelectItem>
            <SelectItem value="performance">Performance</SelectItem>
            <SelectItem value="security">Security</SelectItem>
            <SelectItem value="reliability">Reliability</SelectItem>
            <SelectItem value="maintainability">Maintainability</SelectItem>
            <SelectItem value="api-contract">API Contract</SelectItem>
            <SelectItem value="data-quality">Data Quality</SelectItem>
            <SelectItem value="test-coverage">Test Coverage</SelectItem>
          </SelectContent>
        </Select>

        <Select value={severityFilter} onValueChange={setSeverityFilter}>
          <SelectTrigger className="w-[150px]">
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

        <Select value={resolvedFilter} onValueChange={setResolvedFilter}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="false">Open</SelectItem>
            <SelectItem value="true">Resolved</SelectItem>
          </SelectContent>
        </Select>

        <Button
          onClick={handleScanNow}
          disabled={scanMutation.isPending}
          className="ml-auto"
        >
          {scanMutation.isPending ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          {scanMutation.isPending ? "Scanning..." : "Scan Now"}
        </Button>
      </div>

      {/* Results count */}
      <div className="text-sm text-muted-foreground">
        {issuesData
          ? `Showing ${issuesData.issues.length} of ${issuesData.total} issues`
          : "Loading..."}
      </div>

      {/* Issues Table */}
      <QAIssuesTable issues={issuesData?.issues || []} isLoading={issuesLoading} />

      {/* Pagination */}
      {issuesData && issuesData.total > pageSize && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Page {currentPage} of {Math.ceil(issuesData.total / pageSize)}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setCurrentPage((p) => Math.min(Math.ceil(issuesData.total / pageSize), p + 1))
              }
              disabled={currentPage === Math.ceil(issuesData.total / pageSize)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
