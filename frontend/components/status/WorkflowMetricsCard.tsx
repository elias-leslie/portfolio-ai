"use client";

import { ExpandableCard } from "./ExpandableCard";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, CheckCircle2, XCircle, Clock, AlertCircle } from "lucide-react";
import type { WorkflowMetrics } from "@/lib/api/status";

interface WorkflowMetricsCardProps {
  metrics: WorkflowMetrics | undefined;
}

export function WorkflowMetricsCard({ metrics }: WorkflowMetricsCardProps) {
  if (!metrics) {
    return (
      <ExpandableCard
        title="Workflow Metrics (7 Days)"
        description="Recent workflow execution trends"
        summary="No workflow data available"
        defaultCollapsed={true}
      >
        <p className="text-sm text-muted-foreground">
          No workflow metrics available for the past 7 days.
        </p>
      </ExpandableCard>
    );
  }

  const successRate = metrics.success_rate.toFixed(1);
  const summary = `${metrics.total_workflows_7d} workflows • ${successRate}% success`;

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case "complete":
        return <Badge variant="success">Complete</Badge>;
      case "failed":
        return <Badge variant="destructive">Failed</Badge>;
      case "running":
        return <Badge className="bg-blue-500">Running</Badge>;
      case "blocked":
        return <Badge variant="warning">Blocked</Badge>;
      case "pending":
        return <Badge variant="outline">Pending</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case "complete":
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-600" />;
      case "running":
        return <Clock className="h-4 w-4 text-blue-600" />;
      case "blocked":
        return <AlertCircle className="h-4 w-4 text-yellow-600" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  return (
    <ExpandableCard
      title="Workflow Metrics (7 Days)"
      description="Recent workflow execution trends and performance"
      summary={summary}
      defaultCollapsed={false}
    >
      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm font-medium">Total Workflows</p>
          </div>
          <p className="text-2xl font-bold">{metrics.total_workflows_7d}</p>
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <p className="text-sm font-medium">Success Rate</p>
          </div>
          <p className="text-2xl font-bold text-green-600">{successRate}%</p>
        </div>

        <div className="space-y-1">
          <p className="text-sm font-medium">By Status</p>
          <div className="flex flex-wrap gap-1">
            {Object.entries(metrics.total_by_status).map(([status, count]) => (
              <div key={status} className="text-xs">
                {getStatusBadge(status)} {count}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Workflow Types Summary */}
      {Object.keys(metrics.summary_by_type).length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold mb-3">By Workflow Type</h4>
          <div className="space-y-2">
            {Object.entries(metrics.summary_by_type).map(([workflowType, statusCounts]) => (
              <div key={workflowType} className="flex items-center justify-between p-2 rounded-lg bg-muted/50">
                <span className="text-sm font-medium">{workflowType}</span>
                <div className="flex gap-2">
                  {Object.entries(statusCounts).map(([status, count]) => (
                    <div key={status} className="flex items-center gap-1">
                      {getStatusIcon(status)}
                      <span className="text-xs text-muted-foreground">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Workflows */}
      {metrics.recent_workflows.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-3">Recent Workflows</h4>
          <div className="space-y-2">
            {metrics.recent_workflows.slice(0, 10).map((workflow) => (
              <div
                key={workflow.id}
                className="flex items-center justify-between p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3 flex-1">
                  {getStatusIcon(workflow.status)}
                  <div className="flex-1">
                    <p className="text-sm font-medium">{workflow.type}</p>
                    <p className="text-xs text-muted-foreground">
                      {workflow.created_at
                        ? new Date(workflow.created_at).toLocaleString()
                        : "Unknown time"}
                    </p>
                  </div>
                </div>
                {getStatusBadge(workflow.status)}
              </div>
            ))}
          </div>
        </div>
      )}

      {metrics.recent_workflows.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-4">
          No recent workflows found
        </p>
      )}
    </ExpandableCard>
  );
}
