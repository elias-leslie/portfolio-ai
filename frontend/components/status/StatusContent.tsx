import { RefreshCw } from 'lucide-react'
import { SectionCard } from '@/components/shared/SectionCard'
import { AgentStatsCard } from '@/components/status/AgentStatsCard'
import { APIKeysCard } from '@/components/status/APIKeysCard'
import { APIQuotasCard } from '@/components/status/APIQuotasCard'
import { BeatScheduleCard } from '@/components/status/BeatScheduleCard'
import { CeleryTaskTable } from '@/components/status/CeleryTaskTable'
import { DataSourcesCard } from '@/components/status/DataSourcesCard'
import { LogsCard } from '@/components/status/LogsCard'
import { MaintenanceTable } from '@/components/status/MaintenanceTable'
import { MLModelCard } from '@/components/status/MLModelCard'
import { NewsHealthCard } from '@/components/status/NewsHealthCard'
import { QueueDepthCard } from '@/components/status/QueueDepthCard'
import { ServiceActionDialog } from '@/components/status/ServiceActionDialog'
import { ServiceStatusTable } from '@/components/status/ServiceStatusTable'
import { SourceQualityCard } from '@/components/status/SourceQualityCard'
import { SystemMetricsTable } from '@/components/status/SystemMetricsTable'
import { TableFreshnessCard } from '@/components/status/TableFreshnessCard'
import { WorkflowHealthCard } from '@/components/status/WorkflowHealthCard'
import { WorkflowMetricsCard } from '@/components/status/WorkflowMetricsCard'
import { Button } from '@/components/ui/button'
import type { NewsHealthResponse } from '@/lib/api/news'
import type { DetailedHealthResponse, HealthResponse } from '@/lib/api/status'
import type { SystemResources } from '@/lib/api/resources'
import type { ConnectionBannerConfig, ConnectionState } from '@/lib/utils/connectionBadge'
import type { ActionDialogConfig } from '@/components/status/hooks/useStatusPage'

interface StatusContentProps {
  health: HealthResponse
  connectionState: ConnectionState
  connectionBanner: ConnectionBannerConfig | null
  retryConnection: () => void
  resources: SystemResources | null
  resourcesLoading: boolean
  newsHealth: NewsHealthResponse | null
  newsHealthLoading: boolean
  newsHealthError: Error | null
  refreshNewsHealth: () => void
  detailedHealth: DetailedHealthResponse | null
  actionDialogOpen: boolean
  setActionDialogOpen: (open: boolean) => void
  actionDialogConfig: ActionDialogConfig | null
  isActionLoading: boolean
  triggerRestartService: (serviceName: string) => void
}

export function StatusContent({
  health,
  connectionState,
  connectionBanner,
  retryConnection,
  resources,
  resourcesLoading,
  newsHealth,
  newsHealthLoading,
  newsHealthError,
  refreshNewsHealth,
  detailedHealth,
  actionDialogOpen,
  setActionDialogOpen,
  actionDialogConfig,
  isActionLoading,
  triggerRestartService,
}: StatusContentProps) {
  const services = health.services || {}

  const finbertStatus = newsHealth
    ? newsHealth.finbertAvailable
      ? { label: 'FinBERT Available', variant: 'default' as const }
      : { label: 'FinBERT Unavailable', variant: 'destructive' as const }
    : { label: 'Loading...', variant: 'secondary' as const }

  return (
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
              {connectionState === 'fallback'
                ? 'Falling back to polling every 30s.'
                : 'Live SSE stream disconnected.'}
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
          <ServiceStatusTable
            services={services}
            onRestart={triggerRestartService}
            isRestartDisabled={isActionLoading}
          />
          {resources && <SystemMetricsTable resources={resources} />}
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
  )
}
