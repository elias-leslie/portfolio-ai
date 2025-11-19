"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { History, GitBranch, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import type { WorkflowMetrics } from "@/lib/api/status";

interface WorkflowMetricsCardProps {
  metrics: WorkflowMetrics | undefined;
}

export function WorkflowMetricsCard({ metrics }: WorkflowMetricsCardProps) {
  if (!metrics) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Workflow Metrics (7 Days)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No workflow metrics available</p>
        </CardContent>
      </Card>
    );
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "complete":
        return <Badge variant="success" className="text-xs">{status}</Badge>;
      case "failed":
        return <Badge variant="destructive" className="text-xs">{status}</Badge>;
      case "blocked":
        return <Badge variant="warning" className="text-xs">{status}</Badge>;
      case "running":
        return <Badge variant="default" className="text-xs">{status}</Badge>;
      case "pending":
        return <Badge variant="secondary" className="text-xs">{status}</Badge>;
      default:
        return <Badge variant="outline" className="text-xs">{status}</Badge>;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="h-5 w-5" />
          Workflow Metrics (7 Days)
          <Badge variant="outline" className="ml-auto">
            {metrics.total_workflows_7d} total
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Summary Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <p className="text-sm font-medium">Complete</p>
            </div>
            <p className="text-2xl font-bold text-green-600">
              {metrics.total_by_status.complete || 0}
            </p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <XCircle className="h-4 w-4 text-red-600" />
              <p className="text-sm font-medium">Failed</p>
            </div>
            <p className="text-2xl font-bold text-red-600">
              {metrics.total_by_status.failed || 0}
            </p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <AlertCircle className="h-4 w-4 text-yellow-600" />
              <p className="text-sm font-medium">Blocked</p>
            </div>
            <p className="text-2xl font-bold text-yellow-600">
              {metrics.total_by_status.blocked || 0}
            </p>
          </div>
        </div>

        {/* Success Rate */}
        <div className="border-t pt-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium">7-Day Success Rate</p>
            <p className="text-xl font-bold">
              {metrics.success_rate.toFixed(1)}%
            </p>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div
              className="bg-green-600 h-2.5 rounded-full"
              style={{ width: `${metrics.success_rate}%` }}
            ></div>
          </div>
        </div>

        {/* Summary by Type */}
        {Object.keys(metrics.summary_by_type).length > 0 && (
          <div className="border-t pt-4">
            <p className="text-sm font-medium mb-3">Workflows by Type</p>
            <div className="space-y-2">
              {Object.entries(metrics.summary_by_type).map(([type, statuses]) => {
                const total = Object.values(statuses).reduce((sum, count) => sum + count, 0);
                return (
                  <div key={type} className="flex items-center justify-between text-sm">
                    <span className="font-medium">{type}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">{total} runs</span>
                      <div className="flex gap-1">
                        {statuses.complete > 0 && (
                          <Badge variant="success" className="text-xs">
                            {statuses.complete}
                          </Badge>
                        )}
                        {statuses.failed > 0 && (
                          <Badge variant="destructive" className="text-xs">
                            {statuses.failed}
                          </Badge>
                        )}
                        {statuses.blocked > 0 && (
                          <Badge variant="warning" className="text-xs">
                            {statuses.blocked}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Recent Workflows */}
        {metrics.recent_workflows && metrics.recent_workflows.length > 0 && (
          <div className="border-t pt-4">
            <p className="text-sm font-medium mb-3">Recent Workflows</p>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {metrics.recent_workflows.map((workflow) => (
                <div
                  key={workflow.id}
                  className="flex items-center justify-between p-2 rounded-md border"
                >
                  <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{workflow.type}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {workflow.created_at && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(workflow.created_at).toLocaleDateString()}
                      </span>
                    )}
                    {getStatusBadge(workflow.status)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
