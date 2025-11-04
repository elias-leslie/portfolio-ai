"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Activity, AlertCircle, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { ServiceStatus } from "@/lib/api/status";
import { useServiceLogs } from "@/lib/hooks/useServiceLogs";
import { LogViewer } from "./LogViewer";

interface ServiceCardProps {
  serviceName: string;
  status: ServiceStatus;
  showLogs?: boolean;
}

export function ServiceCard({ serviceName, status, showLogs = true }: ServiceCardProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Only fetch logs when expanded
  const { data: logData, isLoading, error } = useServiceLogs(serviceName, isOpen && showLogs);

  // Format uptime
  const formatUptime = (seconds?: number): string => {
    if (!seconds) return "N/A";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  // Get status badge variant and icon
  const getStatusDisplay = (
    statusValue: string
  ): { variant: "default" | "secondary" | "destructive"; icon: JSX.Element } => {
    switch (statusValue) {
      case "running":
        return {
          variant: "default",
          icon: <CheckCircle2 className="h-4 w-4 text-green-500" />,
        };
      case "degraded":
        return {
          variant: "secondary",
          icon: <AlertCircle className="h-4 w-4 text-yellow-500" />,
        };
      case "down":
        return {
          variant: "destructive",
          icon: <AlertCircle className="h-4 w-4 text-red-500" />,
        };
      default:
        return {
          variant: "secondary",
          icon: <Activity className="h-4 w-4" />,
        };
    }
  };

  const { variant, icon } = getStatusDisplay(status.status);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {icon}
            <span>{status.service_name}</span>
          </div>
          <Badge variant={variant}>{status.status}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Process details */}
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-muted-foreground">PID</div>
            <div className="font-mono">{status.pid || "N/A"}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Uptime</div>
            <div className="font-mono">{formatUptime(status.uptime_seconds)}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Memory</div>
            <div className="font-mono">{status.memory_mb ? `${status.memory_mb} MB` : "N/A"}</div>
          </div>
        </div>

        {/* Status message */}
        {status.message && (
          <div className="text-sm text-muted-foreground border-l-2 border-yellow-500 pl-3">
            {status.message}
          </div>
        )}

        {/* Logs viewer (collapsible) */}
        {showLogs && (
          <Collapsible open={isOpen} onOpenChange={setIsOpen}>
            <CollapsibleTrigger asChild>
              <Button variant="outline" size="sm" className="w-full">
                {isOpen ? (
                  <>
                    <ChevronDown className="mr-2 h-4 w-4" />
                    Hide Logs
                  </>
                ) : (
                  <>
                    <ChevronRight className="mr-2 h-4 w-4" />
                    Show Logs
                  </>
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-4">
              <LogViewer
                lines={logData?.lines || []}
                isLoading={isLoading}
                error={error}
              />
            </CollapsibleContent>
          </Collapsible>
        )}
      </CardContent>
    </Card>
  );
}
