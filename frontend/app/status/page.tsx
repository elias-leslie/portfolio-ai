"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import {
    RefreshCw,
    Wifi,
    WifiOff,
    Radio,
    HardDrive,
    Cpu,
    MemoryStick,
    Trash2,
    ListRestart,
    Lock,
    Unlock,
} from "lucide-react";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useStatusStream } from "@/lib/hooks/useStatusStream";
import { useSystemResources } from "@/lib/hooks/useSystemResources";
import { useNewsHealth } from "@/lib/hooks/useNewsHealth";
import { SystemStatusCard } from "@/components/status/SystemStatusCard";
import { ServiceCard } from "@/components/status/ServiceCard";
import { ResourceCard } from "@/components/status/ResourceCard";
import { DatabasePoolCard } from "@/components/status/DatabasePoolCard";
import { CeleryTaskTable } from "@/components/status/CeleryTaskTable";
import { QueueDepthCard } from "@/components/status/QueueDepthCard";
import { BeatScheduleCard } from "@/components/status/BeatScheduleCard";
import { ServiceActionDialog } from "@/components/status/ServiceActionDialog";
import { DataSourcesCard } from "@/components/status/DataSourcesCard";
import { APIQuotasCard } from "@/components/status/APIQuotasCard";
import { LogsCard } from "@/components/status/LogsCard";
import { SourceQualityCard } from "@/components/status/SourceQualityCard";
import { MLModelCard } from "@/components/status/MLModelCard";
import { MaintenanceCard } from "@/components/status/MaintenanceCard";
import { DataFreshnessCard } from "@/components/status/DataFreshnessCard";
import { APIKeysCard } from "@/components/status/APIKeysCard";
import {
    clearCache,
    refreshWatchlist,
    restartService,
} from "@/lib/api/service-control";
import {
    fetchDetailedHealth,
    DetailedHealthResponse,
} from "@/lib/api/status";

export default function StatusPage() {
    const {
        status: health,
        connectionState,
        isLoading,
        error,
        retryConnection,
    } = useStatusStream();
    const { resources, isLoading: resourcesLoading } = useSystemResources(5000); // Refresh every 5 seconds
    const {
        data: newsHealth,
        isLoading: newsHealthLoading,
        error: newsHealthError,
        refresh: refreshNewsHealth,
    } = useNewsHealth(60000);

    // Fetch detailed health info (day_bars, celery worker, API keys, disk)
    const [detailedHealth, setDetailedHealth] = useState<DetailedHealthResponse | null>(null);
    const [detailedLoading, setDetailedLoading] = useState(false);

    // Fetch detailed health on mount and periodically
    useEffect(() => {
        const fetchDetailed = async () => {
            setDetailedLoading(true);
            try {
                const data = await fetchDetailedHealth();
                setDetailedHealth(data);
            } catch (err) {
                console.error("Failed to fetch detailed health:", err);
            } finally {
                setDetailedLoading(false);
            }
        };

        fetchDetailed();
        const interval = setInterval(fetchDetailed, 30000); // Refresh every 30 seconds

        return () => clearInterval(interval);
    }, []);

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
            alert(
                `Error: ${error instanceof Error ? error.message : "Failed to clear cache"}`,
            );
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
            alert(
                `Error: ${error instanceof Error ? error.message : "Failed to refresh watchlist"}`,
            );
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
                description:
                    "This will remove all cached price data. The cache will be rebuilt on the next price fetch.",
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
                description:
                    "This will trigger a manual refresh of all watchlist data. This may take a few minutes.",
                actionLabel: "Refresh Now",
                onConfirm: handleRefreshWatchlist,
                storageKey,
            });
            setActionDialogOpen(true);
        } else {
            handleRefreshWatchlist();
        }
    };

    // Restart service handler
    const handleRestartService = async (serviceName: string) => {
        setIsActionLoading(true);
        try {
            const result = await restartService(serviceName);
            alert(`Success: ${result.message}`);
        } catch (error) {
            alert(
                `Error: ${error instanceof Error ? error.message : "Failed to restart service"}`,
            );
        } finally {
            setIsActionLoading(false);
        }
    };

    // Restart service with confirmation
    const triggerRestartService = (serviceName: string) => {
        const storageKey = `status.confirm.restart.${serviceName}`;
        if (shouldShowDialog(storageKey)) {
            setActionDialogConfig({
                title: `Restart ${serviceName}`,
                description: `This will restart the ${serviceName} service. The service will be briefly unavailable during the restart.`,
                actionLabel: "Restart Service",
                onConfirm: () => handleRestartService(serviceName),
                storageKey,
            });
            setActionDialogOpen(true);
        } else {
            handleRestartService(serviceName);
        }
    };

    // Connection state badge
    const getConnectionBadge = () => {
        switch (connectionState) {
            case "connected":
                return {
                    icon: <Wifi className="h-3 w-3" />,
                    text: "Live",
                    variant: "default" as const,
                };
            case "connecting":
                return {
                    icon: <Radio className="h-3 w-3 animate-pulse" />,
                    text: "Connecting",
                    variant: "secondary" as const,
                };
            case "disconnected":
                return {
                    icon: <WifiOff className="h-3 w-3" />,
                    text: "Disconnected",
                    variant: "destructive" as const,
                };
            case "fallback":
                return {
                    icon: <RefreshCw className="h-3 w-3" />,
                    text: "Polling",
                    variant: "secondary" as const,
                };
        }
    };

    const connectionBadge = getConnectionBadge();
    const formatDateTime = (value?: string | null) =>
        value ? new Date(value).toLocaleString() : "—";
    const finbertStatus = newsHealth
        ? newsHealth.finbert_available
            ? { label: "FinBERT Available", variant: "default" as const }
            : { label: "FinBERT Unavailable", variant: "destructive" as const }
        : { label: "Loading...", variant: "secondary" as const };
    const fallbackRatePercent = (newsHealth?.fallback_rate_24h ?? 0) * 100;
    const fallbackAvgLatency = newsHealth?.fallback_avg_latency_ms_24h ?? null;
    const fallbackP95Latency = newsHealth?.fallback_p95_latency_ms_24h ?? null;
    const fallbackLastEventAt = newsHealth?.fallback_last_event_at ?? null;
    const lookbackHours =
        newsHealth?.lookback_window_hours ?? newsHealth?.cache_ttl_hours ?? 0;

    if (error) {
        return (
            <div className="container mx-auto p-6">
                <Alert variant="destructive">
                    <AlertTitle>Error Loading Status</AlertTitle>
                    <AlertDescription>
                        {error instanceof Error
                            ? error.message
                            : "Failed to fetch system status"}
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
                        <p className="text-muted-foreground">
                            Loading system status...
                        </p>
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
                    <Badge
                        variant={connectionBadge.variant}
                        className="flex items-center gap-1.5"
                    >
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

            {/* News health card */}
            <Card className="border-border">
                <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <CardTitle className="text-xl">News Health</CardTitle>
                        <p className="text-sm text-muted-foreground">
                            FinBERT availability and cache freshness for the
                            News surface
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge variant={finbertStatus.variant}>
                            {finbertStatus.label}
                        </Badge>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={refreshNewsHealth}
                            disabled={newsHealthLoading}
                        >
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Refresh
                        </Button>
                    </div>
                </CardHeader>
                <CardContent>
                    {newsHealthError ? (
                        <Alert variant="destructive">
                            <AlertTitle>Failed to load news health</AlertTitle>
                            <AlertDescription>
                                {newsHealthError.message ||
                                    "Unable to reach /api/news/health"}
                            </AlertDescription>
                        </Alert>
                    ) : (
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            <div>
                                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                                    Market Last Refresh
                                </p>
                                <p className="text-sm font-medium">
                                    {newsHealthLoading && !newsHealth
                                        ? "Loading..."
                                        : formatDateTime(
                                              newsHealth?.market_last_refreshed_at,
                                          )}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                                    Watchlist Last Refresh
                                </p>
                                <p className="text-sm font-medium">
                                    {newsHealthLoading && !newsHealth
                                        ? "Loading..."
                                        : formatDateTime(
                                              newsHealth?.watchlist_last_refreshed_at,
                                          )}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                                    Headlines (24h)
                                </p>
                                <p className="text-sm font-medium">
                                    {newsHealth?.headlines_24h ?? 0}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    Lookback window: {lookbackHours} hrs
                                </p>
                            </div>
                            <div>
                                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                                    Fallback Usage (24h)
                                </p>
                                <p className="text-sm font-medium">
                                    {newsHealth?.fallback_headlines_24h ?? 0}{" "}
                                    headlines
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    {newsHealth
                                        ? `${fallbackRatePercent.toFixed(1)}% fallback`
                                        : "0% fallback"}
                                </p>
                                {fallbackAvgLatency !== null && (
                                    <p className="text-xs text-muted-foreground">
                                        Avg latency:{" "}
                                        {Math.round(fallbackAvgLatency)} ms
                                    </p>
                                )}
                                {fallbackP95Latency !== null && (
                                    <p className="text-xs text-muted-foreground">
                                        P95 latency:{" "}
                                        {Math.round(fallbackP95Latency)} ms
                                    </p>
                                )}
                                {fallbackLastEventAt && (
                                    <p className="text-xs text-muted-foreground">
                                        Last fallback:{" "}
                                        {formatDateTime(fallbackLastEventAt)}
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Data Sources card */}
            <DataSourcesCard health={health} />

            {/* API Quotas card */}
            <APIQuotasCard health={health} />

            {/* News Source Quality card */}
            <SourceQualityCard />

            {/* ML Model Status card */}
            <MLModelCard />

            {/* API Keys Configuration card */}
            {detailedHealth?.api_keys && detailedHealth.api_keys.length > 0 && (
                <APIKeysCard apiKeys={detailedHealth.api_keys} />
            )}

            {/* Data Freshness card */}
            {detailedHealth?.day_bars_freshness && (
                <DataFreshnessCard freshness={detailedHealth.day_bars_freshness} />
            )}

            {/* Service cards grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {serviceEntries.map(([serviceName, status]) => (
                    <ServiceCard
                        key={serviceName}
                        serviceName={serviceName}
                        status={status}
                        onRestart={triggerRestartService}
                    />
                ))}
            </div>

            {/* System Logs */}
            <LogsCard />

            {/* Empty state */}
            {serviceEntries.length === 0 && (
                <Alert>
                    <AlertTitle>No Services Found</AlertTitle>
                    <AlertDescription>
                        No services are currently being monitored. Check your
                        configuration.
                    </AlertDescription>
                </Alert>
            )}

            {/* System Resources Section */}
            <div className="space-y-4">
                <div>
                    <h2 className="text-2xl font-bold">System Resources</h2>
                    <p className="text-muted-foreground text-sm">
                        Real-time monitoring of system resources (auto-refreshes
                        every 5 seconds)
                    </p>
                </div>

                {resourcesLoading && !resources ? (
                    <div className="text-center py-8">
                        <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                        <p className="text-muted-foreground mt-2">
                            Loading resource data...
                        </p>
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
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-2xl font-bold">Celery Monitoring</h2>
                            <p className="text-muted-foreground text-sm">
                                Task queue and worker status (manual refresh only to
                                avoid performance issues)
                            </p>
                        </div>
                        {detailedHealth?.celery_worker && (
                            <div className="flex items-center gap-2">
                                <Badge
                                    variant={
                                        detailedHealth.celery_worker.active
                                            ? "default"
                                            : "destructive"
                                    }
                                >
                                    {detailedHealth.celery_worker.active
                                        ? "Worker Active"
                                        : "Worker Inactive"}
                                </Badge>
                                {detailedHealth.celery_worker.pool_size && (
                                    <Badge variant="outline">
                                        Pool: {detailedHealth.celery_worker.pool_size}
                                    </Badge>
                                )}
                                {detailedHealth.celery_worker.active_tasks !== undefined &&
                                    detailedHealth.celery_worker.active_tasks !== null && (
                                        <Badge variant="outline">
                                            Active Tasks:{" "}
                                            {detailedHealth.celery_worker.active_tasks}
                                        </Badge>
                                    )}
                            </div>
                        )}
                    </div>
                </div>

                {/* Queue depth and schedule cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <QueueDepthCard />
                    <BeatScheduleCard />
                </div>

                {/* Task table */}
                <CeleryTaskTable />

                {/* Database Maintenance */}
                <MaintenanceCard />
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
