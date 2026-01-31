import { useCallback, useState } from 'react'
import { toast } from 'sonner'
import {
  type BackupRequirementCheck,
  cleanupOldNews,
  triggerMaintenanceTask,
  vacuumDatabase,
  validateIntegrity,
} from '@/lib/api/maintenance'
import { shouldShowDialog } from '@/lib/utils/dialog-helpers'

export function useMaintenanceTasks(
  dryRun: boolean,
  backupCheck: BackupRequirementCheck | null,
  onRefresh: () => void,
) {
  const [triggeringTask, setTriggeringTask] = useState<string | null>(null)
  const [actionDialogOpen, setActionDialogOpen] = useState(false)
  const [actionDialogConfig, setActionDialogConfig] = useState<{
    title: string
    description: string
    actionLabel: string
    onConfirm: () => void
    storageKey?: string
  } | null>(null)
  const [taskResultOpen, setTaskResultOpen] = useState(false)
  const [taskResult, setTaskResult] = useState<{
    taskName: string
    dryRun: boolean
    result: Record<string, unknown> | null
  } | null>(null)

  // File cleanup trigger handler with dry-run support
  const handleFileCleanupTrigger = useCallback(
    async (taskName: string) => {
      setTriggeringTask(taskName)
      try {
        const result = await triggerMaintenanceTask(taskName, {
          dryRun,
          waitForResult: true,
          timeout: 60,
        })

        if (result.result) {
          setTaskResult({
            taskName,
            dryRun,
            result: result.result as Record<string, unknown>,
          })
          setTaskResultOpen(true)
        }

        const isDry = dryRun ? ' (dry run)' : ''
        if (result.status === 'completed') {
          toast.success(`${taskName}${isDry}: ${result.message}`)
        } else if (result.status === 'timeout') {
          toast.warning(`${taskName}${isDry}: Still running...`)
        } else {
          toast.success(result.message)
        }

        if (!dryRun) {
          setTimeout(onRefresh, 2000)
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to trigger task'
        toast.error(`Failed to trigger ${taskName}: ${message}`)
      } finally {
        setTriggeringTask(null)
      }
    },
    [dryRun, onRefresh],
  )

  // Database task triggers
  const createTaskTrigger = useCallback(
    (config: {
      taskId: string
      storageKey: string
      title: string
      dryDescription: string
      liveDescription: string
      dryActionLabel: string
      liveActionLabel: string
      apiCall: (
        isDryRun: boolean,
      ) => Promise<{ status: string; summary?: Record<string, unknown> | null }>
      formatSuccess: (
        result: { status: string; summary?: Record<string, unknown> | null },
        isDryRun: boolean,
      ) => string
    }) => {
      const execute = async () => {
        setTriggeringTask(config.taskId)
        try {
          const result = await config.apiCall(dryRun)
          toast.success(config.formatSuccess(result, dryRun))
          await onRefresh()
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Failed'
          toast.error(`${config.title} failed: ${message}`)
        } finally {
          setTriggeringTask(null)
        }
      }

      const trigger = () => {
        if (!dryRun && backupCheck && !backupCheck.canProceed) {
          toast.error(`Cannot run: ${backupCheck.blockingReason}`)
          return
        }
        if (shouldShowDialog(config.storageKey, !dryRun)) {
          setActionDialogConfig({
            title: config.title,
            description: dryRun
              ? config.dryDescription
              : config.liveDescription,
            actionLabel: dryRun
              ? config.dryActionLabel
              : config.liveActionLabel,
            onConfirm: execute,
            storageKey: dryRun ? config.storageKey : undefined,
          })
          setActionDialogOpen(true)
        } else {
          execute()
        }
      }

      return { trigger, execute }
    },
    [dryRun, backupCheck, onRefresh],
  )

  const cleanupNewsTask = createTaskTrigger({
    taskId: 'cleanup_news',
    storageKey: 'status.confirm.cleanupNews',
    title: 'Cleanup Old News',
    dryDescription:
      'Preview articles older than 90 days that would be deleted.',
    liveDescription:
      '⚠️ DESTRUCTIVE: Permanently delete news articles older than 90 days.',
    dryActionLabel: 'Preview',
    liveActionLabel: 'Delete',
    apiCall: cleanupOldNews,
    formatSuccess: (result, isDryRun) =>
      `Cleanup ${result.status}: ${result.summary?.deleted || 0} articles ${isDryRun ? 'would be' : ''} deleted`,
  })

  const vacuumDatabaseTask = createTaskTrigger({
    taskId: 'vacuum_database',
    storageKey: 'status.confirm.vacuumDatabase',
    title: 'Vacuum Database',
    dryDescription: 'Analyze tables and show potential space savings.',
    liveDescription: 'Optimize all database tables using VACUUM ANALYZE.',
    dryActionLabel: 'Analyze',
    liveActionLabel: 'Vacuum',
    apiCall: vacuumDatabase,
    formatSuccess: (result, isDryRun) =>
      `Vacuum ${result.status}: ${result.summary?.totalReclaimedMb || 0} MB ${isDryRun ? 'could be' : ''} reclaimed`,
  })

  const validateIntegrityTask = createTaskTrigger({
    taskId: 'validate_integrity',
    storageKey: 'status.confirm.validateIntegrity',
    title: 'Validate Integrity',
    dryDescription: 'Check for orphaned records and consistency issues.',
    liveDescription: '⚠️ Check and attempt to fix integrity issues.',
    dryActionLabel: 'Check',
    liveActionLabel: 'Fix',
    apiCall: validateIntegrity,
    formatSuccess: (result, isDryRun) => {
      const summary = result.summary as Record<string, unknown> | null
      const totalErrors =
        typeof summary?.totalErrors === 'number' ? summary.totalErrors : 0
      const totalWarnings =
        typeof summary?.totalWarnings === 'number' ? summary.totalWarnings : 0
      const mode = isDryRun ? 'Check' : 'Validation'
      return `${mode} ${result.status}: ${totalErrors} errors, ${totalWarnings} warnings`
    },
  })

  const handleRunAll = async () => {
    toast.info('Running all maintenance tasks...')
    const fileCleanupTasks = [
      'cleanup_old_logs_task',
      'cleanup_old_backups_task',
      'cleanup_old_models_task',
      'cleanup_solution_state_task',
    ]
    for (const task of fileCleanupTasks) {
      await handleFileCleanupTrigger(task)
    }
    await cleanupNewsTask.execute()
    await vacuumDatabaseTask.execute()
    await validateIntegrityTask.execute()
    toast.success('All maintenance tasks completed')
  }

  return {
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
  }
}
