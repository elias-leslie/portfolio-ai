"use client";

import { RefreshCw, Wifi, WifiOff, Radio } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { useStatusStream } from "@/lib/hooks/useStatusStream";
import { SystemStatusCard } from "@/components/status/SystemStatusCard";
import { ServiceCard } from "@/components/status/ServiceCard";
import { CeleryTaskTable } from "@/components/status/CeleryTaskTable";
import { QueueDepthCard } from "@/components/status/QueueDepthCard";
import { BeatScheduleCard } from "@/components/status/BeatScheduleCard";

export default function StatusPage() {
  const { status: health, connectionState, isLoading, error, retryConnection } = useStatusStream();

  // Connection state badge
  const getConnectionBadge = () => {
    switch (connectionState) {
      case "connected":
        return { icon: <Wifi className="h-3 w-3" />, text: "Live", variant: "default" as const };
      case "connecting":
        return { icon: <Radio className="h-3 w-3 animate-pulse" />, text: "Connecting", variant: "secondary" as const };
      case "disconnected":
        return { icon: <WifiOff className="h-3 w-3" />, text: "Disconnected", variant: "destructive" as const };
      case "fallback":
        return { icon: <RefreshCw className="h-3 w-3" />, text: "Polling", variant: "secondary" as const };
    }
  };

  const connectionBadge = getConnectionBadge();

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive">
          <AlertTitle>Error Loading Status</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : "Failed to fetch system status"}
          </AlertDescription>
        </Alert>
        <Button onClick={retryConnection} className="mt-4">
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry Connection
        </Button>
      </div>
    );
  }

  if (isLoading || !health) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center space-y-4">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
            <p className="text-muted-foreground">Loading system status...</p>
          </div>
        </div>
      </div>
    );
  }

  const services = health.services || {};
  const serviceEntries = Object.entries(services);

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">System Status</h1>
          <p className="text-muted-foreground">
            Real-time monitoring of all services and infrastructure
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={connectionBadge.variant} className="flex items-center gap-1.5">
            {connectionBadge.icon}
            {connectionBadge.text}
          </Badge>
          {connectionState === "fallback" && (
            <Button
              variant="outline"
              size="sm"
              onClick={retryConnection}
            >
              <Wifi className="mr-2 h-4 w-4" />
              Retry Live Connection
            </Button>
          )}
        </div>
      </div>

      {/* System overview card */}
      <SystemStatusCard health={health} />

      {/* Service cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {serviceEntries.map(([serviceName, status]) => (
          <ServiceCard
            key={serviceName}
            serviceName={serviceName}
            status={status}
            showLogs={true}
          />
        ))}
      </div>

      {/* Empty state */}
      {serviceEntries.length === 0 && (
        <Alert>
          <AlertTitle>No Services Found</AlertTitle>
          <AlertDescription>
            No services are currently being monitored. Check your configuration.
          </AlertDescription>
        </Alert>
      )}

      {/* Celery Monitoring Section */}
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold">Celery Monitoring</h2>
          <p className="text-muted-foreground text-sm">
            Task queue and worker status (manual refresh only to avoid performance issues)
          </p>
        </div>

        {/* Queue depth and schedule cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <QueueDepthCard />
          <BeatScheduleCard />
        </div>

        {/* Task table */}
        <CeleryTaskTable />
      </div>
    </div>
  );
}
