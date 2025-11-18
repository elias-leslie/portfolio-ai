"use client";

import { Activity, CheckCircle2, AlertCircle, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { WorkflowHealthInfo } from "@/lib/api/status";
import { ExpandableCard } from "@/components/status/ExpandableCard";

interface WorkflowHealthCardProps {
  workflowHealth: WorkflowHealthInfo | undefined;
}

export function WorkflowHealthCard({ workflowHealth }: WorkflowHealthCardProps) {
  if (!workflowHealth) {
    return (
      <ExpandableCard
        title={
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            <span>Workflow Health</span>
          </div>
        }
        description="Autonomous trading workflow execution status (24h)."
        summary="No workflow data available"
        defaultCollapsed
      >
        <p className="text-sm text-muted-foreground">No workflow health data available.</p>
      </ExpandableCard>
    );
  }

  const summary = `${workflowHealth.total_workflows_24h} workflows • ${workflowHealth.successful_workflows} complete • ${workflowHealth.success_rate.toFixed(1)}% success`;

  return (
    <ExpandableCard
      title={
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          <span>Workflow Health</span>
        </div>
      }
      description="Autonomous trading workflow execution status (24h)."
      summary={summary}
      defaultCollapsed
      actions={<Badge variant={getStatusVariant(workflowHealth.status)}>{getStatusLabel(workflowHealth.status)}</Badge>}
    >
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Total Workflows"
            value={workflowHealth.total_workflows_24h}
            sublabel="Last 24 hours"
          />
          <StatCard
            label="Success Rate"
            value={`${workflowHealth.success_rate.toFixed(1)}%`}
            sublabel={`${workflowHealth.successful_workflows}/${workflowHealth.total_workflows_24h - workflowHealth.blocked_workflows} completed`}
            valueClassName={workflowHealth.success_rate >= 75 ? "text-green-600" : workflowHealth.success_rate >= 50 ? "text-yellow-600" : "text-red-600"}
          />
          <StatCard
            label="Failed"
            value={workflowHealth.failed_workflows}
            sublabel={workflowHealth.failed_workflows > 0 ? "Needs attention" : "No failures"}
            valueClassName={workflowHealth.failed_workflows > 0 ? "text-red-600" : "text-green-600"}
          />
          <StatCard
            label="Blocked"
            value={workflowHealth.blocked_workflows}
            sublabel={workflowHealth.blocked_workflows > 0 ? "Requires action" : "All clear"}
            valueClassName={workflowHealth.blocked_workflows > 0 ? "text-yellow-600" : "text-green-600"}
          />
        </div>

        {workflowHealth.last_successful_workflow && (
          <div className="rounded-lg border p-3">
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <span className="font-medium">Last successful workflow:</span>
              <span className="text-muted-foreground">{workflowHealth.last_successful_type}</span>
              <span className="text-xs text-muted-foreground">({formatTimestamp(workflowHealth.last_successful_workflow)})</span>
            </div>
          </div>
        )}

        {Object.keys(workflowHealth.failures_by_type).length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Badge variant="destructive">{Object.keys(workflowHealth.failures_by_type).length}</Badge>
              <span>Workflow Types with Failures</span>
            </div>
            <div className="space-y-2">
              {Object.entries(workflowHealth.failures_by_type)
                .sort(([, aCount], [, bCount]) => bCount - aCount)
                .map(([workflowType, count]) => (
                  <div
                    key={workflowType}
                    className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <XCircle className="h-4 w-4 text-red-500" />
                      <span className="font-medium capitalize">{workflowType.replace(/_/g, " ")}</span>
                    </div>
                    <Badge variant="destructive">{count} failed</Badge>
                  </div>
                ))}
            </div>
          </div>
        )}

        {Object.keys(workflowHealth.blocked_by_type).length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Badge className="bg-yellow-500 text-white">{Object.keys(workflowHealth.blocked_by_type).length}</Badge>
              <span>Workflow Types Blocked</span>
            </div>
            <div className="space-y-2">
              {Object.entries(workflowHealth.blocked_by_type)
                .sort(([, aCount], [, bCount]) => bCount - aCount)
                .map(([workflowType, count]) => (
                  <div
                    key={workflowType}
                    className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <AlertCircle className="h-4 w-4 text-yellow-500" />
                      <span className="font-medium capitalize">{workflowType.replace(/_/g, " ")}</span>
                    </div>
                    <Badge className="bg-yellow-500 text-white">{count} blocked</Badge>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </ExpandableCard>
  );
}

function StatCard({
  label,
  value,
  sublabel,
  valueClassName = "",
}: {
  label: string;
  value: string | number;
  sublabel?: string;
  valueClassName?: string;
}) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`text-2xl font-bold ${valueClassName}`}>{value}</p>
      {sublabel && <p className="text-xs text-muted-foreground mt-1">{sublabel}</p>}
    </div>
  );
}

function getStatusVariant(status: string): "default" | "destructive" | "secondary" {
  switch (status) {
    case "healthy":
      return "default";
    case "warning":
      return "secondary";
    case "critical":
      return "destructive";
    default:
      return "secondary";
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case "healthy":
      return "Healthy";
    case "warning":
      return "Warning";
    case "critical":
      return "Critical";
    default:
      return status;
  }
}

function formatTimestamp(timestamp: string | null | undefined) {
  if (!timestamp) return "Never";
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  } catch {
    return "Unknown";
  }
}
