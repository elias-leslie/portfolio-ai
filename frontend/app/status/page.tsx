"use client";

import { useState, useEffect } from "react";
import {
    RefreshCw,
    Wifi,
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
import { WorkflowHealthCard } from "@/components/status/WorkflowHealthCard";
import { AgentStatsCard } from "@/components/status/AgentStatsCard";
import { WorkflowMetricsCard } from "@/components/status/WorkflowMetricsCard";
import { NewsHealthCard } from "@/components/status/NewsHealthCard";
import { restartService } from "@/lib/api/service-control";
import {
    fetchDetailedHealth,
    DetailedHealthResponse,
} from "@/lib/api/status";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { PageContainer } from "@/components/shared/PageContainer";
import { getConnectionBadge, getConnectionBanner } from "@/lib/utils/connectionBadge";
import { shouldShowDialog } from "@/lib/utils/dialog-helpers";

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

    // Fetch detailed health on mount and periodically
    useEffect(() => {
        const fetchDetailed = async () => {
            try {
                const data = await fetchDetailedHealth();
                setDetailedHealth(data);
            } catch (err) {
                console.error("Failed to fetch detailed health:", err);
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

    // Connection state badge and banner (using extracted utility)
    const connectionBadge = getConnectionBadge(connectionState, realtimeEnabled);
    const connectionBanner = getConnectionBanner(connectionState, realtimeEnabled, isDataStale);

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

    const finbertStatus = newsHealth
        ? newsHealth.finbertAvailable
            ? { label: "FinBERT Available", variant: "default" as const }
            : { label: "FinBERT Unavailable", variant: "destructive" as const }
        : { label: "Loading...", variant: "secondary" as const };

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

    // NewsHealthCard component used below

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
                    <NewsHealthCard
                        newsHealth={newsHealth}
                        newsHealthLoading={newsHealthLoading}
                        newsHealthError={newsHealthError}
                        finbertStatus={finbertStatus}
                        onRefresh={refreshNewsHealth}
                    />
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
