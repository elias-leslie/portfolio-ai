'use client'

import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { StatusContent } from '@/components/status/StatusContent'
import { StatusHeaderActions } from '@/components/status/StatusHeaderActions'
import { StatusSkeleton } from '@/components/status/StatusSkeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useStatusPage } from '@/components/status/hooks/useStatusPage'
import { getConnectionBanner } from '@/lib/utils/connectionBadge'
import { RefreshCw } from 'lucide-react'

export default function StatusPage() {
  const {
    realtimeEnabled,
    setRealtimeEnabled,
    connectionState,
    retryConnection,
    health,
    isLoading,
    error,
    isDataStale,
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
  } = useStatusPage()

  const connectionBanner = getConnectionBanner(connectionState, realtimeEnabled, isDataStale)

  const headerActions = (
    <StatusHeaderActions
      realtimeEnabled={realtimeEnabled}
      setRealtimeEnabled={setRealtimeEnabled}
      connectionState={connectionState}
      retryConnection={retryConnection}
    />
  )

  const renderShell = (content: React.ReactNode) => (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        title="System Status"
        description="Monitoring of services, workers, and integrations."
        actions={headerActions}
      />
      {content}
    </PageContainer>
  )

  if (error) {
    return renderShell(
      <SectionCard variant="surface">
        <Alert variant="destructive">
          <AlertTitle>Error Loading Status</AlertTitle>
          <AlertDescription>
            {error instanceof Error
              ? error.message
              : 'Failed to fetch system status'}
          </AlertDescription>
        </Alert>
        <Button onClick={retryConnection} className="mt-4">
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry Connection
        </Button>
      </SectionCard>,
    )
  }

  if (isLoading || !health) {
    return renderShell(<StatusSkeleton />)
  }

  return renderShell(
    <StatusContent
      health={health}
      connectionState={connectionState}
      connectionBanner={connectionBanner}
      retryConnection={retryConnection}
      resources={resources}
      resourcesLoading={resourcesLoading}
      newsHealth={newsHealth}
      newsHealthLoading={newsHealthLoading}
      newsHealthError={newsHealthError}
      refreshNewsHealth={refreshNewsHealth}
      detailedHealth={detailedHealth}
      actionDialogOpen={actionDialogOpen}
      setActionDialogOpen={setActionDialogOpen}
      actionDialogConfig={actionDialogConfig}
      isActionLoading={isActionLoading}
      triggerRestartService={triggerRestartService}
    />,
  )
}
