"use client";

import { Activity, Database, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HealthResponse } from "@/lib/api/status";

interface SystemStatusCardProps {
  health: HealthResponse;
}

export function SystemStatusCard({ health }: SystemStatusCardProps) {
  // Calculate overall service health
  const services = health.services || {};
  const serviceCount = Object.keys(services).length;
  const healthyServices = Object.values(services).filter(
    (s) => s.status === "running"
  ).length;

  // Determine overall system status badge
  const getSystemBadge = (): { variant: "default" | "secondary" | "destructive"; text: string } => {
    const healthyRatio = serviceCount > 0 ? healthyServices / serviceCount : 0;

    if (healthyRatio === 1) {
      return { variant: "default", text: "All Systems Operational" };
    } else if (healthyRatio >= 0.5) {
      return { variant: "secondary", text: "Degraded Performance" };
    } else {
      return { variant: "destructive", text: "System Issues" };
    }
  };

  const systemBadge = getSystemBadge();

  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            <span>System Overview</span>
          </div>
          <Badge variant={systemBadge.variant}>{systemBadge.text}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Services */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Activity className="h-4 w-4" />
              Services
            </div>
            <div className="text-2xl font-bold">
              {healthyServices}/{serviceCount}
            </div>
            <div className="text-xs text-muted-foreground">
              {healthyServices === serviceCount
                ? "All services healthy"
                : `${serviceCount - healthyServices} service(s) degraded`}
            </div>
          </div>

          {/* Database */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Database className="h-4 w-4" />
              Database
            </div>
            <div className="text-2xl font-bold">
              {health.checks?.database?.status === "ok" ? "OK" : "Down"}
            </div>
            <div className="text-xs text-muted-foreground">
              {health.checks?.database?.latencyMs
                ? `${health.checks.database.latencyMs}ms latency`
                : "No latency data"}
            </div>
          </div>

          {/* Data Sources */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <TrendingUp className="h-4 w-4" />
              Data Sources
            </div>
            <div className="text-2xl font-bold">
              {Object.values(health.sources || {}).filter((s) => s.status === "ok").length}/
              {Object.keys(health.sources || {}).length}
            </div>
            <div className="text-xs text-muted-foreground">
              {Object.keys(health.sources || {}).length > 0
                ? "External APIs"
                : "No sources configured"}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
