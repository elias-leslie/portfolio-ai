"use client";

import { useState, useEffect } from "react";
import {
    RefreshCw,
    Wifi,
    WifiOff,
    Radio,
    Clock3,
    Newspaper,
} from "lucide-react";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { useStatusStream } from "@/lib/hooks/useStatusStream";
import { useSystemStatus } from "@/lib/hooks/useSystemStatus";
import { useSystemResources } from "@/lib/hooks/useSystemResources";
import { useNewsHealth } from "@/lib/hooks/useNewsHealth";
import { ServiceStatusTable } from "@/components/status/ServiceStatusTable";
import { SystemMetricsTable } from "@/components/status/SystemMetricsTable";
import { CeleryTaskTable } from "@/components/status/CeleryTaskTable";
import { QueueDepthCard } from "@/components/status/QueueDepthCard";
import { BeatScheduleCard } from "@/components/status/BeatScheduleCard";
import { ServiceActionDialog } from "@/components/status/ServiceActionDialog";
import { DataSourcesCard } from "@/components/status/DataSourcesCard";
import { APIQuotasCard } from "@/components/status/APIQuotasCard";
import { LogsCard } from "@/components/status/LogsCard";
import { SourceQualityCard } from "@/components/status/SourceQualityCard";
import { MLModelCard } from "@/components/status/MLModelCard";
import { MaintenanceTable } from "@/components/status/MaintenanceTable";
import { TableFreshnessCard } from "@/components/status/TableFreshnessCard";
import { APIKeysCard } from "@/components/status/APIKeysCard";
import { ExpandableCard } from "@/components/status/ExpandableCard";
import { WorkflowHealthCard } from "@/components/status/WorkflowHealthCard";
import { AgentStatsCard } from "@/components/status/AgentStatsCard";
import { WorkflowMetricsCard } from "@/components/status/WorkflowMetricsCard";
import { restartService } from "@/lib/api/service-control";
import {
    fetchDetailedHealth,
    DetailedHealthResponse,
} from "@/lib/api/status";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { PageContainer } from "@/components/shared/PageContainer";

// Storage key for realtime preference
const REALTIME_STORAGE_KEY = "status.realtimeEnabled";

export default function StatusPage() {
    // Realtime toggle state - defaults to OFF for better performance
    const [realtimeEnabled, setRealtimeEnabled] = useState(() => {
        if (typeof window === "undefined") return false;
        return localStorage.getItem(REALTIME_STORAGE_KEY) === "true";
    });

    // Persist realtime preference
    useEffect(() => {
        localStorage.setItem(REALTIME_STORAGE_KEY, String(realtimeEnabled));
    }, [realtimeEnabled]);

    // Use SSE stream when realtime is enabled, otherwise use polling
    const {
        status: streamStatus,
        connectionState,
        isLoading: streamLoading,
        error: streamError,
        retryConnection,
    } = useStatusStream();

    // Polling fallback (always runs, but we only use it when realtime is off)
    const {
        data: pollingStatus,
        isLoading: pollingLoading,
        error: pollingError,
    } = useSystemStatus();

    // Choose which data source to use
    const health = realtimeEnabled ? streamStatus : pollingStatus;
    const isLoading = realtimeEnabled ? streamLoading : pollingLoading;
    const error = realtimeEnabled ? streamError : pollingError;

    const [lastUpdateTimestamp, setLastUpdateTimestamp] = useState<number | null>(null);
    const [isDataStale, setIsDataStale] = useState(false);

    // Resources polling - slower when realtime is off
    const resourcesInterval = realtimeEnabled ? 5000 : 30000;
    const { resources, isLoading: resourcesLoading } = useSystemResources(resourcesInterval);

    const {
        data: newsHealth,
        isLoading: newsHealthLoading,
        error: newsHealthError,
        refresh: refreshNewsHealth,
    } = useNewsHealth(60000);

    // Fetch detailed health info (day_bars, celery worker, API keys, disk)
    const [detailedHealth, setDetailedHealth] = useState<DetailedHealthResponse | null>(null);
    const [_detailedLoading, setDetailedLoading] = useState(false);

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
        const interval = setInterval(fetchDetailed, 30000);

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

    // Connection state badge (only shown when realtime is enabled)
    const getConnectionBadge = () => {
        if (!realtimeEnabled) {
            return {
                icon: <RefreshCw className="h-3 w-3" />,
                text: "Polling",
                variant: "secondary" as const,
            };
        }
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
        <div className="flex flex-wrap items-center gap-3">
            {/* Realtime Toggle */}
            <div className="flex items-center gap-2">
                <Switch
                    id="realtime-toggle"
                    checked={realtimeEnabled}
                    onCheckedChange={setRealtimeEnabled}
                />
                <Label htmlFor="realtime-toggle" className="cursor-pointer text-sm">
                    Live updates
                </Label>
            </div>

            {/* Connection Badge */}
            <Badge
                variant={connectionBadge.variant}
                className="flex items-center gap-1.5"
            >
                {connectionBadge.icon}
                {connectionBadge.text}
            </Badge>

            {/* Retry button (only when realtime enabled and disconnected) */}
            {realtimeEnabled && (connectionState === "fallback" || connectionState === "disconnected") && (
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
        </div>
    );

    const connectionBanner = (() => {
        if (!realtimeEnabled) return null;
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
                    "Showing backup polling data (30s interval). Retry the live stream for lower latency.",
                icon: <Radio className="h-4 w-4 text-accent" />,
            };
        }
        if (connectionState === "connected" && isDataStale) {
            return {
                tone: "warning" as const,
                title: "No live events detected",
                description:
                    "We haven't received new status events for 10 seconds. Refresh the stream to ensure accuracy.",
                icon: <Clock3 className="h-4 w-4 text-accent" />,
            };
        }
        return null;
    })();

    const formatDateTime = (value?: string | null) =>
        value ? new Date(value).toLocaleString() : "—";

    const finbertStatus = newsHealth
        ? newsHealth.finbertAvailable
            ? { label: "FinBERT Available", variant: "default" as const }
            : { label: "FinBERT Unavailable", variant: "destructive" as const }
        : { label: "Loading...", variant: "secondary" as const };

    const fallbackRatePercent = (newsHealth?.fallbackRate24H ?? 0) * 100;
    const fallbackAvgLatency = newsHealth?.fallbackAvgLatencyMs24H ?? null;
    const fallbackP95Latency = newsHealth?.fallbackP95LatencyMs24H ?? null;
    const fallbackLastEventAt = newsHealth?.fallbackLastEventAt ?? null;
    const lookbackHours =
        newsHealth?.lookbackWindowHours ?? newsHealth?.cacheTtlHours ?? 0;

    const renderShell = (content: React.ReactNode) => (
        <PageContainer className="space-y-10 py-10">
            <PageHeader
                title="System Status"
                description="Monitoring of services, workers, and integrations."
                actions={headerActions}
            />
            {content}
        </PageContainer>
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
            const fallbackCount = newsHealth.fallbackHeadlines24H ?? 0;
            const fallbackSummary = fallbackCount > 0 ? `${fallbackCount} fallback` : "No fallback";
            return `${newsHealth.headlines24H ?? 0} headlines • ${fallbackSummary} • ${finbertStatus.label}`;
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
                                    : formatDateTime(newsHealth?.marketLastRefreshedAt)}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs uppercase tracking-wide text-muted-foreground">
                                Watchlist Last Refresh
                            </p>
                            <p className="text-sm font-medium">
                                {newsHealthLoading && !newsHealth
                                    ? "Loading..."
                                    : formatDateTime(newsHealth?.watchlistLastRefreshedAt)}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs uppercase tracking-wide text-muted-foreground">
                                Headlines (24h)
                            </p>
                            <p className="text-sm font-medium">
                                {newsHealth?.headlines24H ?? 0}
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
                                {newsHealth?.fallbackHeadlines24H ?? 0} headlines
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
                                ? "Falling back to polling every 30s."
                                : "Live SSE stream disconnected."}
                        </span>
                    </div>
                </SectionCard>
            )}

            <SectionCard
                variant="surface"
                title="Overview"
                description="Services and system resources at a glance."
            >
                <div className="space-y-6">
                    {/* Services Table */}
                    <ServiceStatusTable
                        services={services}
                        onRestart={triggerRestartService}
                        isRestartDisabled={isActionLoading}
                    />

                    {/* System Metrics Table */}
                    {resources && (
                        <SystemMetricsTable resources={resources} />
                    )}

                    {resourcesLoading && !resources && (
                        <div className="text-center py-4">
                            <RefreshCw className="h-5 w-5 animate-spin mx-auto text-muted-foreground" />
                            <p className="text-muted-foreground text-sm mt-2">Loading resources...</p>
                        </div>
                    )}
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
                    {detailedHealth?.apiKeys && detailedHealth.apiKeys.length > 0 && (
                        <APIKeysCard apiKeys={detailedHealth.apiKeys} />
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
                    <WorkflowHealthCard workflowHealth={detailedHealth?.workflowHealth} />
                    <AgentStatsCard stats={health?.agentStats} />
                    <div className="md:col-span-2 lg:col-span-3">
                        <WorkflowMetricsCard metrics={detailedHealth?.workflowMetrics} />
                    </div>
                </div>
            </SectionCard>

            <MaintenanceTable />

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
        <SectionCard variant="surface" title="Loading status" description="Fetching telemetry...">
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
