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
    Clock3,
    Newspaper,
} from "lucide-react";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { useStatusStream } from "@/lib/hooks/useStatusStream";
import { useSystemResources } from "@/lib/hooks/useSystemResources";
import { useNewsHealth } from "@/lib/hooks/useNewsHealth";
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
import { MaintenanceStatusCard } from "@/components/status/MaintenanceStatusCard";
import { TableFreshnessCard } from "@/components/status/TableFreshnessCard";
import { APIKeysCard } from "@/components/status/APIKeysCard";
import { ExpandableCard } from "@/components/status/ExpandableCard";
import { WorkflowHealthCard } from "@/components/status/WorkflowHealthCard";
import { AgentStatsCard } from "@/components/status/AgentStatsCard";
import { WorkflowMetricsCard } from "@/components/status/WorkflowMetricsCard";
import {
    clearCache,
    refreshWatchlist,
    restartService,
} from "@/lib/api/service-control";
import {
    fetchDetailedHealth,
    DetailedHealthResponse,
} from "@/lib/api/status";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { cn } from "@/lib/utils";

export default function StatusPage() {
    const {
        status: health,
        connectionState,
        isLoading,
        error,
        retryConnection,
    } = useStatusStream();
    const [lastUpdateTimestamp, setLastUpdateTimestamp] = useState<number | null>(null);
    const [isDataStale, setIsDataStale] = useState(false);
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

    useEffect(() => {
        if (!health) {
            return;
        }
        setLastUpdateTimestamp(Date.now());
    }, [health]);

    useEffect(() => {
        if (lastUpdateTimestamp === null) {
            return;
        }
        setIsDataStale(false);
        const timeout = window.setTimeout(() => setIsDataStale(true), 10000);
        return () => window.clearTimeout(timeout);
    }, [lastUpdateTimestamp]);

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
            toast.success(result.message ?? "Price cache cleared");
        } catch (error) {
            const message =
                error instanceof Error ? error.message : "Failed to clear cache";
            toast.error(`Failed to clear cache: ${message}`);
            throw error instanceof Error ? error : new Error(message);
        } finally {
            setIsActionLoading(false);
        }
    };

    // Refresh watchlist handler
    const handleRefreshWatchlist = async () => {
        setIsActionLoading(true);
        try {
            const result = await refreshWatchlist();
            toast.success(result.message ?? "Watchlist refresh triggered");
        } catch (error) {
            const message =
                error instanceof Error
                    ? error.message
                    : "Failed to refresh watchlist";
            toast.error(`Failed to refresh watchlist: ${message}`);
            throw error instanceof Error ? error : new Error(message);
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
            toast.success(result.message ?? `${serviceName} restart requested`);
        } catch (error) {
            const message =
                error instanceof Error
                    ? error.message
                    : "Failed to restart service";
            toast.error(`Failed to restart ${serviceName}: ${message}`);
            throw error instanceof Error ? error : new Error(message);
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
    const headerActions = (
        <div className="flex flex-wrap items-center gap-2">
            <Badge
                variant={connectionBadge.variant}
                className="flex items-center gap-1.5"
            >
                {connectionBadge.icon}
                {connectionBadge.text}
            </Badge>
            {(connectionState === "fallback" || connectionState === "disconnected") && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={retryConnection}
                    className="flex items-center gap-1"
                >
                    <Wifi className="h-4 w-4" />
                    Retry live
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
    );
    const connectionBanner = (() => {
        if (connectionState === "disconnected") {
            return {
                tone: "danger" as const,
                title: "Live stream disconnected",
                description:
                    "We lost connection to the SSE stream. Reconnect to resume real-time updates.",
                icon: <WifiOff className="h-4 w-4 text-loss" />,
            };
        }
        if (connectionState === "fallback") {
            return {
                tone: "warning" as const,
                title: "Live stream unavailable",
                description:
                    "Showing backup polling data (5s interval). Retry the live stream for lower latency.",
                icon: <Radio className="h-4 w-4 text-accent" />,
            };
        }
        if (connectionState === "connected" && isDataStale) {
            return {
                tone: "warning" as const,
                title: "No live events detected",
                description:
                    "We haven’t received new status events for 10 seconds. Refresh the stream to ensure accuracy.",
                icon: <Clock3 className="h-4 w-4 text-accent" />,
            };
        }
        return null;
    })();
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

    const renderShell = (content: React.ReactNode) => (
        <div className="bg-bg">
            <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
                <PageHeader
                    title="System Status"
                    description="Real-time monitoring of services, workers, and integrations."
                    actions={headerActions}
                />
                {content}
            </div>
        </div>
    );

    if (error) {
        return renderShell(
            <SectionCard variant="surface">
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
            </SectionCard>
        );
    }

    if (isLoading || !health) {
        return renderShell(<StatusSkeleton />);
    }

    const services = health.services || {};
    const serviceEntries = Object.entries(services);

    const renderNewsHealthCard = () => {
        const summary = (() => {
            if (newsHealthError) {
                return newsHealthError.message || "Failed to load telemetry";
            }
            if (newsHealthLoading && !newsHealth) {
                return "Loading telemetry...";
            }
            if (!newsHealth) {
                return "Waiting for news telemetry";
            }
            const fallbackCount = newsHealth.fallback_headlines_24h ?? 0;
            const fallbackSummary = fallbackCount > 0 ? `${fallbackCount} fallback` : "No fallback";
            return `${newsHealth.headlines_24h ?? 0} headlines • ${fallbackSummary} • ${finbertStatus.label}`;
        })();

        return (
            <ExpandableCard
                title={
                    <div className="flex items-center gap-2">
                        <Newspaper className="h-5 w-5" />
                        <span>News Health</span>
                    </div>
                }
                description="FinBERT availability and cache freshness for the News surface."
                summary={summary}
                defaultCollapsed
                actions={
                    <div className="flex items-center gap-2">
                        <Badge variant={finbertStatus.variant}>{finbertStatus.label}</Badge>
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
                }
            >
                {newsHealthError ? (
                    <Alert variant="destructive">
                        <AlertTitle>Failed to load news health</AlertTitle>
                        <AlertDescription>
                            {newsHealthError.message || "Unable to reach /api/news/health"}
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
                                    : formatDateTime(newsHealth?.market_last_refreshed_at)}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs uppercase tracking-wide text-muted-foreground">
                                Watchlist Last Refresh
                            </p>
                            <p className="text-sm font-medium">
                                {newsHealthLoading && !newsHealth
                                    ? "Loading..."
                                    : formatDateTime(newsHealth?.watchlist_last_refreshed_at)}
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
                                {newsHealth?.fallback_headlines_24h ?? 0} headlines
                            </p>
                            <p className="text-xs text-muted-foreground">
                                {newsHealth
                                    ? `${fallbackRatePercent.toFixed(1)}% fallback`
                                    : "0% fallback"}
                            </p>
                            {fallbackAvgLatency !== null && (
                                <p className="text-xs text-muted-foreground">
                                    Avg latency: {Math.round(fallbackAvgLatency)} ms
                                </p>
                            )}
                            {fallbackP95Latency !== null && (
                                <p className="text-xs text-muted-foreground">
                                    P95 latency: {Math.round(fallbackP95Latency)} ms
                                </p>
                            )}
                            {fallbackLastEventAt && (
                                <p className="text-xs text-muted-foreground">
                                    Last fallback: {formatDateTime(fallbackLastEventAt)}
                                </p>
                            )}
                        </div>
                    </div>
                )}
            </ExpandableCard>
        );
    };


    return renderShell(
        <>
            {connectionBanner && (
                <SectionCard
                    variant="surface"
                    padding="sm"
                    title={connectionBanner.title}
                    description={connectionBanner.description}
                    actions={
                        <Button variant="outline" size="sm" onClick={retryConnection}>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Retry Stream
                        </Button>
                    }
                >
                    <div className="flex items-center gap-2 text-sm">
                        {connectionBanner.icon}
                        <span>
                            {connectionState === "fallback"
                                ? "Falling back to polling every 5s."
                                : "Live SSE stream disconnected."}
                        </span>
                    </div>
                </SectionCard>
            )}

            <SectionCard
                variant="surface"
                title="Overview"
                description="Operational snapshot across services and resources."
            >
                <div className="space-y-6">
                    {serviceEntries.length > 0 ? (
                        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
                            {serviceEntries.map(([serviceName, status]) => (
                                <ServiceCard
                                    key={serviceName}
                                    serviceName={serviceName}
                                    status={status}
                                    onRestart={triggerRestartService}
                                />
                            ))}
                        </div>
                    ) : (
                        <Alert>
                            <AlertTitle>No Services Found</AlertTitle>
                            <AlertDescription>
                                No services are currently being monitored. Check your configuration.
                            </AlertDescription>
                        </Alert>
                    )}
                    <ResourceOverview
                        resources={resources}
                        resourcesLoading={resourcesLoading}
                    />
                </div>
            </SectionCard>

            <SectionCard
                variant="surface"
                title="Data Pipelines"
                description="Upstream vendors, data freshness, and credentials."
            >
                <div className="space-y-4">
                    <DataSourcesCard health={health} />
                    <TableFreshnessCard />
                    <APIQuotasCard health={health} />
                    {detailedHealth?.api_keys && detailedHealth.api_keys.length > 0 && (
                        <APIKeysCard apiKeys={detailedHealth.api_keys} />
                    )}
                </div>
            </SectionCard>

            <SectionCard
                variant="surface"
                title="Scheduled Tasks"
                description="Worker health, queue depth, and beat schedules."
            >
                <div className="space-y-4">
                    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                        <QueueDepthCard />
                        <BeatScheduleCard />
                    </div>
                    <CeleryTaskTable />
                </div>
            </SectionCard>

            <SectionCard
                variant="surface"
                title="News Sources"
                description="Sentiment, source quality, and article-quality models."
            >
                <div className="space-y-4">
                    {renderNewsHealthCard()}
                    <SourceQualityCard />
                    <MLModelCard />
                </div>
            </SectionCard>

            <SectionCard
                variant="surface"
                title="Multi-Agent Workflows"
                description="Autonomous trading workflows with AI agent collaboration and execution tracking."
            >
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <WorkflowHealthCard workflowHealth={detailedHealth?.workflow_health} />
                    <AgentStatsCard stats={health?.agent_stats} />
                    <div className="md:col-span-2 lg:col-span-3">
                        <WorkflowMetricsCard metrics={detailedHealth?.workflow_metrics} />
                    </div>
                </div>
            </SectionCard>

            <SectionCard
                variant="surface"
                title="Maintenance"
                description="Database cleanup, integrity automation, and system monitoring."
            >
                <MaintenanceCard />
                <MaintenanceStatusCard />
            </SectionCard>

            <SectionCard
                variant="surface"
                title="Unified Logging"
                description="Centralized logs with filtering and restart controls."
            >
                <LogsCard />
            </SectionCard>

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
        </>
    );
}

function StatusSkeleton() {
    return (
        <SectionCard variant="surface" title="Loading status" description="Fetching live telemetry...">
            <div className="space-y-4">
                <div className="h-10 w-48 rounded-lg bg-surface-muted/50 animate-pulse" />
                <div className="grid gap-4 md:grid-cols-3">
                    {Array.from({ length: 3 }).map((_, index) => (
                        <div
                            key={`status-skeleton-${index}`}
                            className="h-24 rounded-xl bg-surface-muted/40 animate-pulse"
                        />
                    ))}
                </div>
            </div>
        </SectionCard>
    );
}

function ResourceOverview({
    resources,
    resourcesLoading,
}: {
    resources: ReturnType<typeof useSystemResources>["resources"];
    resourcesLoading: boolean;
}) {
    if (resourcesLoading && !resources) {
        return (
            <div className="text-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                <p className="text-muted-foreground mt-2">Loading resource data...</p>
            </div>
        );
    }

    if (!resources) {
        return null;
    }

    return (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
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
    );
}
