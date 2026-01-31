'use client'

import { CheckCircle2, Database, RefreshCw, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  type BackupRequirementCheck,
  checkBackupRequirements,
  getMaintenanceLastRun,
  type LastRunSummary,
} from '@/lib/api/maintenance'
import { BackupStatusBadge } from './maintenance/BackupStatusBadge'
import { TaskSection } from './maintenance/TaskSection'
import type { ActionDialogConfig } from './maintenance/types'
import { useMaintenanceTasks } from './maintenance/useMaintenanceTasks'
import { formatTaskSummary } from './maintenance/utils'
import { ServiceActionDialog } from './ServiceActionDialog'

export function MaintenanceCard() {
  const [lastRunSummary, setLastRunSummary] = useState<LastRunSummary | null>(
    null,
  )
  const [isFetching, setIsFetching] = useState(false)
  const [dryRun, setDryRun] = useState(true)
  const [backupCheck, setBackupCheck] = useState<BackupRequirementCheck | null>(
    null,
  )
  const [isCheckingBackup, setIsCheckingBackup] = useState(false)
  const [actionDialogOpen, setActionDialogOpen] = useState(false)
  const [actionDialogConfig] = useState<ActionDialogConfig | null>(null)

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

  const checkBackupStatus = useCallback(async () => {
    setIsCheckingBackup(true)
    try {
      const check = await checkBackupRequirements(24, true)
      setBackupCheck(check)
      if (!check.canProceed) {
        toast.warning(
          `Backup check: ${check.blockingReason || 'Requirements not met'}`,
          { duration: 6000 },
        )
      }
    } catch (error) {
      console.error('Failed to check backup requirements:', error)
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

  useEffect(() => {
    fetchLastRunData()
  }, [fetchLastRunData])

  useEffect(() => {
    if (!dryRun) {
      checkBackupStatus()
    } else {
      setBackupCheck(null)
    }
  }, [dryRun, checkBackupStatus])

  const {
    triggeringTask,
    cleanupNewsTask,
    vacuumDatabaseTask,
    validateIntegrityTask,
    actionDialogOpen: hookActionDialogOpen,
    setActionDialogOpen: setHookActionDialogOpen,
    actionDialogConfig: hookActionDialogConfig,
  } = useMaintenanceTasks(dryRun, backupCheck, fetchLastRunData)

  // Use hook's dialog state if available, otherwise use local state
  const dialogOpen = hookActionDialogOpen || actionDialogOpen
  const setDialogOpen = (open: boolean) => {
    setHookActionDialogOpen(open)
    setActionDialogOpen(open)
  }
  const dialogConfig = hookActionDialogConfig || actionDialogConfig

  const overviewSummary = [
    formatTaskSummary(
      'Cleanup',
      lastRunSummary?.tasks?.cleanupOldNewsTask ||
        lastRunSummary?.tasks?.cleanupNews,
    ),
    formatTaskSummary(
      'Vacuum',
      lastRunSummary?.tasks?.vacuumDatabaseTask ||
        lastRunSummary?.tasks?.vacuumDatabase,
    ),
    formatTaskSummary(
      'Integrity',
      lastRunSummary?.tasks?.validateIntegrityTask ||
        lastRunSummary?.tasks?.validateIntegrity,
    ),
  ].join(' • ')

  return (
    <>
      <ExpandableCard
        title="Database Maintenance"
        description="Cleanup, optimize, and validate database integrity."
        summary={overviewSummary}
        defaultCollapsed
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Switch
                id="dry-run"
                checked={dryRun}
                onCheckedChange={setDryRun}
              />
              <Label htmlFor="dry-run" className="cursor-pointer">
                Dry Run
              </Label>
            </div>
            {!dryRun && (
              <div className="flex items-center gap-1.5">
                <BackupStatusBadge
                  isCheckingBackup={isCheckingBackup}
                  backupCheck={backupCheck}
                />
              </div>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={fetchLastRunData}
              disabled={isFetching}
              title="Refresh last run summary"
            >
              <RefreshCw
                className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`}
              />
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <TaskSection
            title="Cleanup Old News"
            description="Remove news articles older than 90 days"
            icon={<Trash2 className="h-5 w-5 text-warning" />}
            lastRun={
              lastRunSummary?.tasks?.cleanupOldNewsTask ||
              lastRunSummary?.tasks?.cleanupNews ||
              null
            }
            onTrigger={cleanupNewsTask.trigger}
            isLoading={triggeringTask === 'cleanup_news'}
          />

          <TaskSection
            title="Vacuum Database"
            description="Optimize tables and reclaim disk space"
            icon={<Database className="h-5 w-5 text-accent" />}
            lastRun={
              lastRunSummary?.tasks?.vacuumDatabaseTask ||
              lastRunSummary?.tasks?.vacuumDatabase ||
              null
            }
            onTrigger={vacuumDatabaseTask.trigger}
            isLoading={triggeringTask === 'vacuum_database'}
          />

          <TaskSection
            title="Validate Data Integrity"
            description="Check for orphaned records and consistency issues"
            icon={<CheckCircle2 className="h-5 w-5 text-gain" />}
            lastRun={
              lastRunSummary?.tasks?.validateIntegrityTask ||
              lastRunSummary?.tasks?.validateIntegrity ||
              null
            }
            onTrigger={validateIntegrityTask.trigger}
            isLoading={triggeringTask === 'validate_integrity'}
          />
        </div>
      </ExpandableCard>

      {dialogConfig && (
        <ServiceActionDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          title={dialogConfig.title}
          description={dialogConfig.description}
          actionLabel={dialogConfig.actionLabel}
          onConfirm={dialogConfig.onConfirm}
          storageKey={dialogConfig.storageKey}
        />
      )}
    </>
  )
}
