'use client'

import {
  AlertCircle,
  CheckCircle2,
  GitBranch,
  History,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { WorkflowMetrics } from '@/lib/api/status'

interface WorkflowMetricsCardProps {
  metrics: WorkflowMetrics | undefined
}

export function WorkflowMetricsCard({ metrics }: WorkflowMetricsCardProps) {
  if (!metrics) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Recent Workflow Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No workflow metrics available
          </p>
        </CardContent>
      </Card>
    )
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'complete':
        return (
          <Badge variant="success" className="text-xs">
            {status}
          </Badge>
        )
      case 'failed':
        return (
          <Badge variant="destructive" className="text-xs">
            {status}
          </Badge>
        )
      case 'blocked':
        return (
          <Badge variant="warning" className="text-xs">
            {status}
          </Badge>
        )
      case 'running':
        return (
          <Badge variant="default" className="text-xs">
            {status}
          </Badge>
        )
      case 'pending':
        return (
          <Badge variant="secondary" className="text-xs">
            {status}
          </Badge>
        )
      default:
        return (
          <Badge variant="outline" className="text-xs">
            {status}
          </Badge>
        )
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="h-5 w-5" />
          Recent Workflow Activity
          <Badge variant="outline" className="ml-auto">
            {metrics.totalWorkflows7D} total
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Summary Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <CheckCircle2 className="h-4 w-4 text-gain" />
              <p className="text-sm font-medium">Complete</p>
            </div>
            <p className="text-2xl font-bold text-gain">
              {metrics.totalByStatus.complete || 0}
            </p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <XCircle className="h-4 w-4 text-loss" />
              <p className="text-sm font-medium">Failed</p>
            </div>
            <p className="text-2xl font-bold text-loss">
              {metrics.totalByStatus.failed || 0}
            </p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <AlertCircle className="h-4 w-4 text-warning" />
              <p className="text-sm font-medium">Blocked</p>
            </div>
            <p className="text-2xl font-bold text-warning">
              {metrics.totalByStatus.blocked || 0}
            </p>
          </div>
        </div>

        {/* Success Rate */}
        <div className="border-t pt-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium">7-Day Success Rate</p>
            <p className="text-xl font-bold">
              {metrics.successRate.toFixed(1)}%
            </p>
          </div>
          <div className="w-full bg-surface-muted rounded-full h-2.5">
            <div
              className="bg-gain h-2.5 rounded-full"
              style={{ width: `${metrics.successRate}%` }}
            ></div>
          </div>
        </div>

        {/* Summary by Type */}
        {Object.keys(metrics.summaryByType).length > 0 && (
          <div className="border-t pt-4">
            <p className="text-sm font-medium mb-3">Workflows by Type</p>
            <div className="space-y-2">
              {Object.entries(metrics.summaryByType).map(([type, statuses]) => {
                const total = Object.values(statuses).reduce(
                  (sum, count) => sum + count,
                  0,
                )
                return (
                  <div
                    key={type}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="font-medium">{type}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">
                        {total} runs
                      </span>
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
                )
              })}
            </div>
          </div>
        )}

        {/* Recent Workflows */}
        {metrics.recentWorkflows && metrics.recentWorkflows.length > 0 && (
          <div className="border-t pt-4">
            <p className="text-sm font-medium mb-3">Recent Workflows</p>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {metrics.recentWorkflows.map((workflow) => (
                <div
                  key={workflow.id}
                  className="flex items-center justify-between p-2 rounded-md border"
                >
                  <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{workflow.type}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {workflow.createdAt && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(workflow.createdAt).toLocaleDateString()}
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
  )
}
