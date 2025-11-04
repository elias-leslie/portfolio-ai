"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useSystemStatus } from "@/lib/hooks/useSystemStatus";
import { SystemStatusCard } from "@/components/status/SystemStatusCard";
import { ServiceCard } from "@/components/status/ServiceCard";

export default function StatusPage() {
  const { data: health, isLoading, error, refetch, dataUpdatedAt } = useSystemStatus();

  // Calculate "last updated" time
  const getLastUpdated = (): string => {
    if (!dataUpdatedAt) return "Never";
    const secondsAgo = Math.floor((Date.now() - dataUpdatedAt) / 1000);
    if (secondsAgo < 10) return "Just now";
    if (secondsAgo < 60) return `${secondsAgo}s ago`;
    const minutesAgo = Math.floor(secondsAgo / 60);
    return `${minutesAgo}m ago`;
  };

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive">
          <AlertTitle>Error Loading Status</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : "Failed to fetch system status"}
          </AlertDescription>
        </Alert>
        <Button onClick={() => refetch()} className="mt-4">
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
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
        <div className="flex items-center gap-4">
          <div className="text-sm text-muted-foreground">
            Last updated: {getLastUpdated()}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
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
    </div>
  );
}
