"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GitBranch, CheckCircle2, XCircle, AlertCircle, Clock } from "lucide-react";
import type { WorkflowHealthInfo } from "@/lib/api/status";

interface WorkflowHealthCardProps {
  workflowHealth: WorkflowHealthInfo | undefined;
}

export function WorkflowHealthCard({ workflowHealth }: WorkflowHealthCardProps) {
  if (!workflowHealth) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Workflow Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No workflow health data available</p>
        </CardContent>
      </Card>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
        return "bg-status-success";
      case "warning":
        return "bg-status-warning";
      case "critical":
        return "bg-status-error";
      default:
        return "bg-surface-muted";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return <CheckCircle2 className="h-4 w-4 text-status-success" />;
      case "warning":
        return <AlertCircle className="h-4 w-4 text-status-warning" />;
      case "critical":
        return <XCircle className="h-4 w-4 text-status-error" />;
      default:
        return <AlertCircle className="h-4 w-4 text-text-muted" />;
    }
  };

  const getSuccessRateColor = (rate: number) => {
    if (rate >= 80) return "text-status-success";
    if (rate >= 50) return "text-status-warning";
    return "text-status-error";
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitBranch className="h-5 w-5" />
          Workflow Health
          <Badge className={getStatusColor(workflowHealth.status)}>
            {workflowHealth.status.toUpperCase()}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Total Workflows 24h */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm font-medium">Total (24h)</p>
            </div>
            <p className="text-2xl font-bold">{workflowHealth.totalWorkflows24H}</p>
          </div>

          {/* Success Rate */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              {getStatusIcon(workflowHealth.status)}
              <p className="text-sm font-medium">Success Rate</p>
            </div>
            <p className={`text-2xl font-bold ${getSuccessRateColor(workflowHealth.successRate)}`}>
              {workflowHealth.successRate}%
            </p>
          </div>

          {/* Successful Workflows */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-status-success" />
              <p className="text-sm font-medium">Successful</p>
            </div>
            <div className="flex items-center gap-2">
              <p className="text-xl font-semibold">{workflowHealth.successfulWorkflows}</p>
              <Badge variant="success" className="text-xs">
                Complete
              </Badge>
            </div>
          </div>

          {/* Failed Workflows */}
          {workflowHealth.failedWorkflows > 0 && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <XCircle className="h-4 w-4 text-status-error" />
                <p className="text-sm font-medium">Failed</p>
              </div>
              <div className="flex items-center gap-2">
                <p className="text-xl font-semibold">{workflowHealth.failedWorkflows}</p>
                <Badge variant="destructive" className="text-xs">
                  Failed
                </Badge>
              </div>
            </div>
          )}

          {/* Blocked Workflows */}
          {workflowHealth.blockedWorkflows > 0 && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-status-warning" />
                <p className="text-sm font-medium">Blocked</p>
              </div>
              <div className="flex items-center gap-2">
                <p className="text-xl font-semibold">{workflowHealth.blockedWorkflows}</p>
                <Badge variant="warning" className="text-xs">
                  Blocked
                </Badge>
              </div>
            </div>
          )}

          {/* Last Successful Workflow */}
          {workflowHealth.lastSuccessfulWorkflow && (
            <div className="space-y-1 col-span-2">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Last Successful</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">
                  {workflowHealth.lastSuccessfulType || "Unknown Type"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {new Date(workflowHealth.lastSuccessfulWorkflow).toLocaleString()}
                </p>
              </div>
            </div>
          )}

          {/* Failures by Type */}
          {Object.keys(workflowHealth.failuresByType).length > 0 && (
            <div className="space-y-1 col-span-2 border-t pt-3">
              <p className="text-sm font-medium text-status-error">Failures by Type:</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(workflowHealth.failuresByType).map(([type, count]) => (
                  <Badge key={type} variant="destructive" className="text-xs">
                    {type}: {count}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Blocked by Type */}
          {Object.keys(workflowHealth.blockedByType).length > 0 && (
            <div className="space-y-1 col-span-2 border-t pt-3">
              <p className="text-sm font-medium text-status-warning">Blocked by Type:</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(workflowHealth.blockedByType).map(([type, count]) => (
                  <Badge key={type} variant="warning" className="text-xs">
                    {type}: {count}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
