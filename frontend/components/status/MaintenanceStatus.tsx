'use client'

import { AlertCircle, CheckCircle2, Database, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import { DatabaseSizeCard } from '@/components/status/maintenance/DatabaseSizeCard'
import { DiskSpaceCard } from '@/components/status/maintenance/DiskSpaceCard'
import { ScheduledTasksCard } from '@/components/status/maintenance/ScheduledTasksCard'
import { TaskTriggerSection } from '@/components/status/maintenance/TaskTriggerSection'
import type {
  DatabaseSize,
  DatabaseSizeResponse,
  DiskSpaceInfo,
  DiskSpaceResponse,
  ScheduledTask,
  ScheduleResponse,
} from '@/components/status/maintenance/types'
import { API_BASE_URL } from '@/components/status/maintenance/utils'
import { ServiceActionDialog } from '@/components/status/ServiceActionDialog'
import { Button } from '@/components/ui/button'
import {
  getMaintenanceLastRun,
  type LastRunSummary,
} from '@/lib/api/maintenance'
import { shouldShowDialog } from '@/lib/utils/dialog-helpers'

/**
 * MaintenanceStatus Component
 *
 * Displays:
 * - Last run times for each maintenance task
 * - Next scheduled run times
 * - Current disk space usage with progress bars
 * - Current database size and top tables
 * - Manual trigger buttons for each task
 * - Confirmation dialogs before triggering tasks
 */
export function MaintenanceStatus() {
  // State for maintenance tasks
  const [lastRunSummary, setLastRunSummary] = useState<LastRunSummary | null>(
    null,
  )
  const [isFetching, setIsFetching] = useState(false)
  const [isTriggering, setIsTriggering] = useState(false)

  // State for disk space and database info
  const [diskSpace, setDiskSpace] = useState<DiskSpaceInfo[] | null>(null)
  const [diskLoading, setDiskLoading] = useState(false)

  const [database, setDatabase] = useState<DatabaseSize | null>(null)
  const [databaseLoading, setDatabaseLoading] = useState(false)

  const [scheduledTasks, setScheduledTasks] = useState<ScheduledTask[] | null>(
    null,
  )
  const [tasksLoading, setTasksLoading] = useState(false)

  // Dialog state
  const [actionDialogOpen, setActionDialogOpen] = useState(false)
  const [actionDialogConfig, setActionDialogConfig] = useState<{
    title: string
    description: string
    actionLabel: string
    onConfirm: () => void
    storageKey?: string
  } | null>(null)

  const fetchLastRunData = useCallback(async () => {
    setIsFetching(true)
    try {
      const data = await getMaintenanceLastRun()
      setLastRunSummary(data)
    } catch (error) {
      console.error('Failed to fetch maintenance data:', error)
    } finally {
      setIsFetching(false)
    }
  }, [])

  const fetchDiskSpace = useCallback(async () => {
    setDiskLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/maintenance/disk-space`)
      if (!response.ok) throw new Error('Failed to fetch disk space')
      const data: DiskSpaceResponse = await response.json()
      setDiskSpace(data.disks)
    } catch (error) {
      console.error('Failed to fetch disk space:', error)
    } finally {
      setDiskLoading(false)
    }
  }, [])

  const fetchDatabaseSize = useCallback(async () => {
    setDatabaseLoading(true)
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/maintenance/database-size`,
      )
      if (!response.ok) throw new Error('Failed to fetch database size')
      const data: DatabaseSizeResponse = await response.json()
      setDatabase(data.database)
    } catch (error) {
      console.error('Failed to fetch database size:', error)
    } finally {
      setDatabaseLoading(false)
    }
  }, [])

  const fetchScheduledTasks = useCallback(async () => {
    setTasksLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/maintenance/schedule`)
      if (!response.ok) throw new Error('Failed to fetch scheduled tasks')
      const data: ScheduleResponse = await response.json()
      setScheduledTasks(data.tasks)
    } catch (error) {
      console.error('Failed to fetch scheduled tasks:', error)
    } finally {
      setTasksLoading(false)
    }
  }, [])

  const fetchAllData = useCallback(
    async () =>
      Promise.all([
        fetchLastRunData(),
        fetchDiskSpace(),
        fetchDatabaseSize(),
        fetchScheduledTasks(),
      ]),
    [fetchDatabaseSize, fetchDiskSpace, fetchLastRunData, fetchScheduledTasks],
  )

  useEffect(() => {
    fetchAllData()
    const interval = setInterval(fetchAllData, 30000)
    return () => clearInterval(interval)
  }, [fetchAllData])

  // Generic trigger handler
  const triggerTask = (
    taskName: string,
    taskLabel: string,
    handler: () => Promise<void>,
  ) => {
    const storageKey = `status.confirm.maintenance.${taskName}`
    if (shouldShowDialog(storageKey)) {
      setActionDialogConfig({
        title: `Trigger ${taskLabel}`,
        description: `This will manually trigger the ${taskLabel} maintenance task. The task will run in the background.`,
        actionLabel: 'Trigger Now',
        onConfirm: handler,
        storageKey,
      })
      setActionDialogOpen(true)
    } else {
      handler()
    }
  }

  const handleTriggerTask = async (taskName: string) => {
    setIsTriggering(true)
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/maintenance/trigger/${taskName}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        },
      )
      if (!response.ok) throw new Error(`Failed to trigger ${taskName}`)
      await response.json()
      toast.success(`${taskName} triggered successfully`)
      await fetchLastRunData()
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to trigger task',
      )
    } finally {
      setIsTriggering(false)
    }
  }

  return (
    <>
      <ExpandableCard
        title="Maintenance Overview"
        description="Scheduled tasks, disk usage, and database size monitoring."
        defaultCollapsed={false}
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <DiskSpaceCard disks={diskSpace} isLoading={diskLoading} />
            <DatabaseSizeCard database={database} isLoading={databaseLoading} />
          </div>
          <ScheduledTasksCard tasks={scheduledTasks} isLoading={tasksLoading} />
          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchAllData}
              disabled={isFetching}
            >
              <RefreshCw
                className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`}
              />
              Refresh
            </Button>
          </div>
        </div>
      </ExpandableCard>

      <ExpandableCard
        title="Manual Task Triggers"
        description="Manually trigger maintenance tasks on demand."
        defaultCollapsed={true}
      >
        <div className="space-y-3">
          <TaskTriggerSection
            title="Cleanup Old News"
            description="Remove news articles older than 90 days"
            icon={
              <AlertCircle className="h-5 w-5 text-status-warning flex-shrink-0" />
            }
            lastRun={
              lastRunSummary?.tasks?.cleanupOldNewsTask ||
              lastRunSummary?.tasks?.cleanupNews ||
              null
            }
            onTrigger={() =>
              triggerTask('cleanup_news', 'Cleanup News', () =>
                handleTriggerTask('cleanup_news'),
              )
            }
            isLoading={isTriggering}
          />
          <TaskTriggerSection
            title="Vacuum Database"
            description="Optimize tables and reclaim disk space"
            icon={
              <Database className="h-5 w-5 text-status-info flex-shrink-0" />
            }
            lastRun={
              lastRunSummary?.tasks?.vacuumDatabaseTask ||
              lastRunSummary?.tasks?.vacuumDatabase ||
              null
            }
            onTrigger={() =>
              triggerTask('vacuum_database', 'Vacuum Database', () =>
                handleTriggerTask('vacuum_database'),
              )
            }
            isLoading={isTriggering}
          />
          <TaskTriggerSection
            title="Validate Data Integrity"
            description="Check for orphaned records and consistency issues"
            icon={
              <CheckCircle2 className="h-5 w-5 text-status-success flex-shrink-0" />
            }
            lastRun={
              lastRunSummary?.tasks?.validateIntegrityTask ||
              lastRunSummary?.tasks?.validateIntegrity ||
              null
            }
            onTrigger={() =>
              triggerTask('validate_integrity', 'Validate Integrity', () =>
                handleTriggerTask('validate_integrity'),
              )
            }
            isLoading={isTriggering}
          />
        </div>
      </ExpandableCard>

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
    </>
  )
}
