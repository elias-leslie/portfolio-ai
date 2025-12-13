"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Activity, CheckCircle2, XCircle, Clock, DollarSign, Cpu, ArrowRight } from "lucide-react";
import type { AgentStats } from "@/lib/api/status";
import { useTelemetrySummary } from "@/lib/hooks/useAgentTelemetry";

interface AgentStatsCardProps {
  stats: AgentStats | undefined;
}

function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
}

export function AgentStatsCard({ stats }: AgentStatsCardProps) {
  // Fetch telemetry for token usage (7 day summary)
  const { data: telemetry } = useTelemetrySummary(7);

  if (!stats && !telemetry) {
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

  const successRate = stats && stats.total_runs > 0
    ? ((stats.completed_runs / stats.total_runs) * 100).toFixed(1)
    : telemetry ? telemetry.success_rate.toFixed(1) : "0.0";

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
            <p className="text-2xl font-bold">{stats?.total_runs ?? telemetry?.total_runs ?? 0}</p>
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
              <p className="text-xl font-semibold">{stats?.completed_runs ?? telemetry?.successful_runs ?? 0}</p>
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
              <p className="text-xl font-semibold">{stats?.failed_runs ?? telemetry?.failed_runs ?? 0}</p>
              <Badge variant="destructive" className="text-xs">
                Failed
              </Badge>
            </div>
          </div>

          {/* Average Duration */}
          {(stats?.avg_duration_s !== undefined || telemetry?.avg_duration_ms !== undefined) && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Avg Duration</p>
              </div>
              <p className="text-lg font-semibold">
                {stats?.avg_duration_s !== undefined
                  ? `${stats.avg_duration_s.toFixed(1)}s`
                  : telemetry?.avg_duration_ms !== undefined
                  ? `${(telemetry.avg_duration_ms / 1000).toFixed(1)}s`
                  : "N/A"}
              </p>
            </div>
          )}

          {/* Average Cost */}
          {stats?.avg_cost_usd !== undefined && stats?.avg_cost_usd !== null && (
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

          {/* Total Tokens (7d) */}
          {telemetry && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Tokens (7d)</p>
              </div>
              <p className="text-lg font-semibold">
                {formatNumber(telemetry.total_tokens)}
              </p>
            </div>
          )}
        </div>

        {/* Link to Agent Hub */}
        <div className="mt-4 pt-4 border-t">
          <Link href="/agent-hub">
            <Button variant="outline" size="sm" className="w-full">
              Open Agent Hub
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
