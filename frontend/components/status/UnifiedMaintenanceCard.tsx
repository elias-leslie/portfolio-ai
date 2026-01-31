'use client'

import {
  Calendar,
  Loader2,
  PlayCircle,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  type BackupRequirementCheck,
  type CacheStatusResponse,
  checkBackupRequirements,
  type DatabaseSizeResponse,
  type DiskSpaceResponse,
  type FileCleanupStatusResponse,
  getCacheStatus,
  getFileCleanupStatus,
  getMaintenanceDatabaseSize,
  getMaintenanceDiskSpace,
  getMaintenanceLastRun,
  getMaintenanceSchedule,
  type LastRunSummary,
  type MaintenanceScheduleResponse,
} from '@/lib/api/maintenance'
import { CacheCleanupSection } from './maintenance/CacheCleanupSection'
import { DatabaseMaintenanceSection } from './maintenance/DatabaseMaintenanceSection'
import { DataCleanupSection } from './maintenance/DataCleanupSection'
import { FileCleanupSection } from './maintenance/FileCleanupSection'
import { SystemStatusSection } from './maintenance/SystemStatusSection'
import { useMaintenanceTasks } from './maintenance/useMaintenanceTasks'
import { ServiceActionDialog } from './ServiceActionDialog'

export function UnifiedMaintenanceCard() {
  // State for all data sources
  const [fileCleanup, setFileCleanup] =
    useState<FileCleanupStatusResponse | null>(null)
  const [lastRunSummary, setLastRunSummary] = useState<LastRunSummary | null>(
    null,
  )
  const [diskSpace, setDiskSpace] = useState<DiskSpaceResponse | null>(null)
  const [dbSize, setDbSize] = useState<DatabaseSizeResponse | null>(null)
  const [schedule, setSchedule] = useState<MaintenanceScheduleResponse | null>(
    null,
  )
  const [backupCheck, setBackupCheck] = useState<BackupRequirementCheck | null>(
    null,
  )
  const [cacheStatus, setCacheStatus] = useState<CacheStatusResponse | null>(
    null,
  )

  // UI state
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [dryRun, setDryRun] = useState(true)
  const [isCheckingBackup, setIsCheckingBackup] = useState(false)

  // Fetch all data
  const fetchAllData = useCallback(async () => {
    try {
      const [fileData, lastRun, diskData, dbData, scheduleData, cacheData] =
        await Promise.all([
          getFileCleanupStatus(),
          getMaintenanceLastRun(),
          getMaintenanceDiskSpace(),
          getMaintenanceDatabaseSize(),
          getMaintenanceSchedule(),
          getCacheStatus(),
        ])
      setFileCleanup(fileData)
      setLastRunSummary(lastRun)
      setDiskSpace(diskData)
      setDbSize(dbData)
      setSchedule(scheduleData)
      setCacheStatus(cacheData)
    } catch (error) {
      console.error('Failed to fetch maintenance data:', error)
      toast.error('Failed to load maintenance data')
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchAllData()
  }, [fetchAllData])

  const checkBackupStatus = useCallback(async () => {
    setIsCheckingBackup(true)
    try {
      const check = await checkBackupRequirements(24, true)
      setBackupCheck(check)
      if (!check.canProceed) {
        toast.warning(
          `Backup check: ${check.blockingReason || 'Requirements not met'}`,
        )
      }
    } catch {
      toast.error('Could not verify backup status')
      setBackupCheck({
        backupExists: false,
        backupRecent: false,
        backupVerified: false,
        backupName: null,
        backupAgeHours: null,
        canProceed: false,
        blockingReason: 'Could not verify backup status',
        warnings: [],
      })
    } finally {
      setIsCheckingBackup(false)
    }
  }, [])

  // Check backup when dry-run is toggled off
  useEffect(() => {
    if (!dryRun) {
      checkBackupStatus()
    } else {
      setBackupCheck(null)
    }
  }, [dryRun, checkBackupStatus])

  const handleRefresh = () => {
    setIsRefreshing(true)
    fetchAllData()
  }

  // Use maintenance tasks hook
  const {
    triggeringTask,
    handleFileCleanupTrigger,
    cleanupNewsTask,
    vacuumDatabaseTask,
    validateIntegrityTask,
    handleRunAll,
    actionDialogOpen,
    setActionDialogOpen,
    actionDialogConfig,
    taskResultOpen,
    setTaskResultOpen,
    taskResult,
  } = useMaintenanceTasks(dryRun, backupCheck, fetchAllData)

  // Summary text
  const getSummary = () => {
    if (isLoading) return 'Loading...'
    if (diskSpace?.alerts?.length)
      return `⚠️ ${diskSpace.alerts.length} disk alert(s)`
    return 'Ready'
  }

  const canRunLive = !dryRun && backupCheck?.canProceed === true
  const liveBlocked = !dryRun && backupCheck !== null && !backupCheck.canProceed

  return (
    <>
      <ExpandableCard
        title="Maintenance"
        description="Unified file cleanup, database maintenance, and system monitoring"
        summary={getSummary()}
        defaultCollapsed
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Switch
                id="dry-run-unified"
                checked={dryRun}
                onCheckedChange={setDryRun}
              />
              <Label
                htmlFor="dry-run-unified"
                className="cursor-pointer text-sm"
              >
                Dry Run
              </Label>
            </div>

            {!dryRun && (
              <div className="flex items-center gap-1.5">
                {isCheckingBackup ? (
                  <Badge
                    variant="secondary"
                    className="flex items-center gap-1"
                  >
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Checking...
                  </Badge>
                ) : canRunLive ? (
                  <Badge
                    variant="default"
                    className="flex items-center gap-1 bg-status-success"
                  >
                    <ShieldCheck className="h-3 w-3" />
                    Backup OK
                  </Badge>
                ) : (
                  <Badge
                    variant="destructive"
                    className="flex items-center gap-1"
                  >
                    <ShieldAlert className="h-3 w-3" />
                    {backupCheck?.blockingReason?.split('.')[0] || 'No backup'}
                  </Badge>
                )}
              </div>
            )}

            <Button
              size="sm"
              variant="default"
              onClick={handleRunAll}
              disabled={triggeringTask !== null || liveBlocked}
              title="Run all maintenance tasks"
            >
              <PlayCircle className="h-4 w-4 mr-1" />
              Run All
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
              title="Refresh all data"
            >
              <RefreshCw
                className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`}
              />
            </Button>
          </div>
        }
      >
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-2">
            <SystemStatusSection
              fileCleanup={fileCleanup}
              dbSize={dbSize}
              cacheStatus={cacheStatus}
              diskSpace={diskSpace}
            />

            <FileCleanupSection
              fileCleanup={fileCleanup}
              triggeringTask={triggeringTask}
              onTrigger={handleFileCleanupTrigger}
            />

            <CacheCleanupSection
              cacheStatus={cacheStatus}
              triggeringTask={triggeringTask}
              onTrigger={handleFileCleanupTrigger}
            />

            <DataCleanupSection
              triggeringTask={triggeringTask}
              onTrigger={handleFileCleanupTrigger}
            />

            <DatabaseMaintenanceSection
              lastRunSummary={lastRunSummary}
              triggeringTask={triggeringTask}
              liveBlocked={liveBlocked}
              onCleanupNews={cleanupNewsTask.trigger}
              onVacuumDatabase={vacuumDatabaseTask.trigger}
              onValidateIntegrity={validateIntegrityTask.trigger}
            />

            {/* Scheduled Tasks Footer */}
            <div className="mt-6 pt-4 border-t">
              <details>
                <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  {schedule?.totalCount || 0} Scheduled Tasks
                </summary>
                <div className="mt-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {schedule &&
                    Object.entries(schedule.scheduledTasks).map(
                      ([name, task]) => (
                        <div key={name} className="text-xs border rounded p-2">
                          <div className="font-medium truncate">{name}</div>
                          <div className="text-muted-foreground">
                            {task.schedule}
                          </div>
                        </div>
                      ),
                    )}
                </div>
              </details>
            </div>
          </div>
        )}
      </ExpandableCard>

      {/* Confirmation Dialog */}
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

      {/* Task Results Dialog */}
      {taskResult && (
        <ServiceActionDialog
          open={taskResultOpen}
          onOpenChange={setTaskResultOpen}
          title={`${taskResult.dryRun ? 'Dry Run Preview' : 'Task Complete'}: ${taskResult.taskName.replace(/_/g, ' ')}`}
          description={
            taskResult.dryRun
              ? 'No changes were made. Review what would happen below.'
              : 'Task completed. See results below.'
          }
          actionLabel="Done"
          onConfirm={() => setTaskResultOpen(false)}
        >
          <div className="my-4 max-h-80 overflow-auto border rounded p-3 bg-muted/30">
            <div className="space-y-2 text-sm">
              {taskResult.result &&
                Object.entries(taskResult.result).map(([key, value]) => {
                  if (key === 'task_id' || key === 'success') return null
                  if (
                    key === 'details' &&
                    Array.isArray(value) &&
                    value.length > 0
                  ) {
                    return (
                      <details
                        key={key}
                        className="border rounded p-2 bg-background"
                      >
                        <summary className="cursor-pointer font-medium">
                          Details ({value.length} items)
                        </summary>
                        <div className="mt-2 space-y-1 pl-2 max-h-40 overflow-auto">
                          {value.slice(0, 50).map((item, idx) => (
                            <div
                              key={idx}
                              className="text-xs text-muted-foreground font-mono truncate"
                            >
                              {typeof item === 'object'
                                ? JSON.stringify(item)
                                : String(item)}
                            </div>
                          ))}
                          {value.length > 50 && (
                            <div className="text-xs text-muted-foreground italic">
                              ... and {value.length - 50} more
                            </div>
                          )}
                        </div>
                      </details>
                    )
                  }
                  if (
                    key === 'details' &&
                    Array.isArray(value) &&
                    value.length === 0
                  )
                    return null
                  return (
                    <div
                      key={key}
                      className="flex justify-between py-1 border-b border-border/30 last:border-0"
                    >
                      <span className="text-muted-foreground capitalize">
                        {key.replace(/_/g, ' ')}:
                      </span>
                      <span className="font-mono font-medium">
                        {typeof value === 'boolean'
                          ? value
                            ? 'Yes'
                            : 'No'
                          : String(value)}
                      </span>
                    </div>
                  )
                })}
            </div>
          </div>
        </ServiceActionDialog>
      )}
    </>
  )
}
