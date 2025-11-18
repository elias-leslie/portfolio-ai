"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, CheckCircle2, XCircle, Clock, DollarSign } from "lucide-react";
import type { AgentStats } from "@/lib/api/status";

interface AgentStatsCardProps {
  stats: AgentStats | undefined;
}

export function AgentStatsCard({ stats }: AgentStatsCardProps) {
  if (!stats) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Agent Execution Stats
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No agent statistics available</p>
        </CardContent>
      </Card>
    );
  }

  const successRate = stats.total_runs > 0
    ? ((stats.completed_runs / stats.total_runs) * 100).toFixed(1)
    : "0.0";

  const getSuccessRateColor = (rate: number) => {
    if (rate >= 80) return "text-green-600";
    if (rate >= 50) return "text-yellow-600";
    return "text-red-600";
  };

  const rate = parseFloat(successRate);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          Agent Execution Stats
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Total Runs */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm font-medium">Total Runs</p>
            </div>
            <p className="text-2xl font-bold">{stats.total_runs}</p>
          </div>

          {/* Success Rate */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CheckCircle2 className={`h-4 w-4 ${getSuccessRateColor(rate)}`} />
              <p className="text-sm font-medium">Success Rate</p>
            </div>
            <p className={`text-2xl font-bold ${getSuccessRateColor(rate)}`}>
              {successRate}%
            </p>
          </div>

          {/* Completed Runs */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <p className="text-sm font-medium">Completed</p>
            </div>
            <div className="flex items-center gap-2">
              <p className="text-xl font-semibold">{stats.completed_runs}</p>
              <Badge variant="success" className="text-xs">
                Success
              </Badge>
            </div>
          </div>

          {/* Failed Runs */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-600" />
              <p className="text-sm font-medium">Failed</p>
            </div>
            <div className="flex items-center gap-2">
              <p className="text-xl font-semibold">{stats.failed_runs}</p>
              <Badge variant="destructive" className="text-xs">
                Failed
              </Badge>
            </div>
          </div>

          {/* Average Duration */}
          {stats.avg_duration_s !== undefined && stats.avg_duration_s !== null && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Avg Duration</p>
              </div>
              <p className="text-lg font-semibold">
                {stats.avg_duration_s.toFixed(1)}s
              </p>
            </div>
          )}

          {/* Average Cost */}
          {stats.avg_cost_usd !== undefined && stats.avg_cost_usd !== null && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Avg Cost</p>
              </div>
              <p className="text-lg font-semibold">
                ${stats.avg_cost_usd.toFixed(4)}
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
