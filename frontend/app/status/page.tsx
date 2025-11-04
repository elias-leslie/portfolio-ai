"use client";

import { useState } from "react";
import { RefreshCw, Wifi, WifiOff, Radio, HardDrive, Cpu, MemoryStick, Trash2, ListRestart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { useStatusStream } from "@/lib/hooks/useStatusStream";
import { useSystemResources } from "@/lib/hooks/useSystemResources";
import { SystemStatusCard } from "@/components/status/SystemStatusCard";
import { ServiceCard } from "@/components/status/ServiceCard";
import { ResourceCard } from "@/components/status/ResourceCard";
import { DatabasePoolCard } from "@/components/status/DatabasePoolCard";
import { CeleryTaskTable } from "@/components/status/CeleryTaskTable";
import { QueueDepthCard } from "@/components/status/QueueDepthCard";
import { BeatScheduleCard } from "@/components/status/BeatScheduleCard";
import { ServiceActionDialog } from "@/components/status/ServiceActionDialog";
import { clearCache, refreshWatchlist } from "@/lib/api/service-control";

export default function StatusPage() {
  const { status: health, connectionState, isLoading, error, retryConnection } = useStatusStream();
  const { resources, isLoading: resourcesLoading } = useSystemResources(5000); // Refresh every 5 seconds

  const [actionDialogOpen, setActionDialogOpen] = useState(false);
  const [actionDialogConfig, setActionDialogConfig] = useState<{
    title: string;
    description: string;
    actionLabel: string;
    onConfirm: () => void;
    storageKey?: string;
  } | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);

  // Check if user has disabled confirmation dialogs
  const shouldShowDialog = (storageKey: string) => {
    if (typeof window === "undefined") return true;
    return !localStorage.getItem(storageKey);
  };

  // Clear cache handler
  const handleClearCache = async () => {
    setIsActionLoading(true);
    try {
      const result = await clearCache();
      alert(`Success: ${result.message}`);
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : "Failed to clear cache"}`);
    } finally {
      setIsActionLoading(false);
    }
  };

  // Refresh watchlist handler
  const handleRefreshWatchlist = async () => {
    setIsActionLoading(true);
    try {
      const result = await refreshWatchlist();
      alert(`Success: ${result.message}`);
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : "Failed to refresh watchlist"}`);
    } finally {
      setIsActionLoading(false);
    }
  };

  // Clear cache with confirmation
  const triggerClearCache = () => {
    const storageKey = "status.confirm.clearCache";
    if (shouldShowDialog(storageKey)) {
      setActionDialogConfig({
        title: "Clear Price Cache",
        description: "This will remove all cached price data. The cache will be rebuilt on the next price fetch.",
        actionLabel: "Clear Cache",
        onConfirm: handleClearCache,
        storageKey,
      });
      setActionDialogOpen(true);
    } else {
      handleClearCache();
    }
  };

  // Refresh watchlist with confirmation
  const triggerRefreshWatchlist = () => {
    const storageKey = "status.confirm.refreshWatchlist";
    if (shouldShowDialog(storageKey)) {
      setActionDialogConfig({
        title: "Refresh Watchlist",
        description: "This will trigger a manual refresh of all watchlist data. This may take a few minutes.",
        actionLabel: "Refresh Now",
        onConfirm: handleRefreshWatchlist,
        storageKey,
      });
      setActionDialogOpen(true);
    } else {
      handleRefreshWatchlist();
    }
  };

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
          <Button
            variant="outline"
            size="sm"
            onClick={triggerClearCache}
            disabled={isActionLoading}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Clear Cache
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={triggerRefreshWatchlist}
            disabled={isActionLoading}
          >
            <ListRestart className="mr-2 h-4 w-4" />
            Refresh Watchlist
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

      {/* System Resources Section */}
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold">System Resources</h2>
          <p className="text-muted-foreground text-sm">
            Real-time monitoring of system resources (auto-refreshes every 5 seconds)
          </p>
        </div>

        {resourcesLoading && !resources ? (
          <div className="text-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
            <p className="text-muted-foreground mt-2">Loading resource data...</p>
          </div>
        ) : resources ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <ResourceCard
              title="Disk Usage"
              percent={resources.disk.percent_used}
              status={resources.disk.status}
              details={`${resources.disk.used_gb.toFixed(1)} GB / ${resources.disk.total_gb.toFixed(1)} GB used`}
              icon={<HardDrive className="h-5 w-5" />}
            />
            <ResourceCard
              title="Memory Usage"
              percent={resources.memory.percent_used}
              status={resources.memory.status}
              details={`${resources.memory.used_gb.toFixed(1)} GB / ${resources.memory.total_gb.toFixed(1)} GB used`}
              icon={<MemoryStick className="h-5 w-5" />}
            />
            <ResourceCard
              title="CPU Usage"
              percent={resources.cpu.percent_used}
              status={resources.cpu.status}
              details={`${resources.cpu.cores} cores available`}
              icon={<Cpu className="h-5 w-5" />}
            />
            <DatabasePoolCard
              poolSize={resources.database_pool.pool_size}
              checkedOut={resources.database_pool.checked_out}
              overflow={resources.database_pool.overflow}
              percent={resources.database_pool.percent_used}
              status={resources.database_pool.status}
            />
          </div>
        ) : null}
      </div>

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

      {/* Service Action Dialog */}
      {actionDialogConfig && (
        <ServiceActionDialog
          open={actionDialogOpen}
          onOpenChange={setActionDialogOpen}
          title={actionDialogConfig.title}
          description={actionDialogConfig.description}
          actionLabel={actionDialogConfig.actionLabel}
          onConfirm={actionDialogConfig.onConfirm}
          storageKey={actionDialogConfig.storageKey}
        />
      )}
    </div>
  );
}
