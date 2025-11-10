"use client";

import { useState } from "react";
import { TrendingUp, CheckCircle2, AlertCircle, XCircle, Clock, ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { HealthResponse } from "@/lib/api/status";

interface DataSourcesCardProps {
  health: HealthResponse;
}

export function DataSourcesCard({ health }: DataSourcesCardProps) {
  const [healthyOpen, setHealthyOpen] = useState(false);
  const [unhealthyOpen, setUnhealthyOpen] = useState(true);

  const sources = health.sources || {};
  const sourceEntries = Object.entries(sources);
  const healthySources = sourceEntries.filter(([_, s]) => s.status === "ok");
  const unhealthySources = sourceEntries.filter(([_, s]) => s.status !== "ok");

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "ok":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "degraded":
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      case "down":
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ok":
        return <Badge className="bg-green-500 text-white">Healthy</Badge>;
      case "degraded":
        return <Badge className="bg-yellow-500 text-white">Degraded</Badge>;
      case "down":
        return <Badge variant="destructive">Down</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const formatTimestamp = (timestamp: string | null | undefined) => {
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
  };

  if (sourceEntries.length === 0) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            <span>Data Sources</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No data sources configured. Check your source configuration files.
          </p>
        </CardContent>
      </Card>
    );
  }

  const renderSourceRow = (sourceName: string, sourceHealth: typeof sources[string]) => (
    <div
      key={sourceName}
      className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
    >
      <div className="flex items-center gap-3 flex-1">
        {getStatusIcon(sourceHealth.status)}
        <div className="flex-1">
          <div className="font-medium capitalize">
            {sourceName.replace(/_/g, " ")}
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Last success: {formatTimestamp(sourceHealth.last_success)}
            </div>
            {sourceHealth.success_rate !== null && (
              <div>Success rate: {sourceHealth.success_rate.toFixed(1)}%</div>
            )}
            {sourceHealth.avg_latency_ms !== null && (
              <div>Avg latency: {sourceHealth.avg_latency_ms}ms</div>
            )}
          </div>
          {sourceHealth.in_cooldown && (
            <div className="flex items-center gap-1 text-xs text-yellow-600 mt-1">
              <AlertCircle className="h-3 w-3" />
              In cooldown ({sourceHealth.cooldown_remaining_seconds}s remaining)
            </div>
          )}
          {sourceHealth.rate_limit_hits > 0 && (
            <div className="text-xs text-orange-600 mt-1">
              Rate limit hits: {sourceHealth.rate_limit_hits}
            </div>
          )}
        </div>
      </div>
      <div>{getStatusBadge(sourceHealth.status)}</div>
    </div>
  );

  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            <span>Data Sources</span>
          </div>
          <Badge variant={healthySources.length === sourceEntries.length ? "default" : "secondary"}>
            {healthySources.length}/{sourceEntries.length} Healthy
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Unhealthy sources section */}
        {unhealthySources.length > 0 && (
          <Collapsible open={unhealthyOpen} onOpenChange={setUnhealthyOpen}>
            <CollapsibleTrigger asChild>
              <Button variant="outline" className="w-full justify-between">
                <div className="flex items-center gap-2">
                  {unhealthyOpen ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  <span className="font-semibold">Unhealthy Data Sources</span>
                </div>
                <Badge variant="destructive">{unhealthySources.length}</Badge>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3">
              <div className="space-y-3">
                {unhealthySources
                  .sort(([aName], [bName]) => aName.localeCompare(bName))
                  .map(([sourceName, sourceHealth]) =>
                    renderSourceRow(sourceName, sourceHealth)
                  )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* Healthy sources section */}
        {healthySources.length > 0 && (
          <Collapsible open={healthyOpen} onOpenChange={setHealthyOpen}>
            <CollapsibleTrigger asChild>
              <Button variant="outline" className="w-full justify-between">
                <div className="flex items-center gap-2">
                  {healthyOpen ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  <span className="font-semibold">Healthy Data Sources</span>
                </div>
                <Badge className="bg-green-500 text-white">
                  {healthySources.length}
                </Badge>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3">
              <div className="space-y-3">
                {healthySources
                  .sort(([aName], [bName]) => aName.localeCompare(bName))
                  .map(([sourceName, sourceHealth]) =>
                    renderSourceRow(sourceName, sourceHealth)
                  )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}
      </CardContent>
    </Card>
  );
}
