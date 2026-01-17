import { useState } from 'react'
import { toast } from 'sonner'
import {
  DB_TASK_API_FUNCTIONS,
  DB_TASK_DIALOG_CONFIGS,
} from '@/components/status/maintenanceTaskConfig'
import { triggerMaintenanceTask } from '@/lib/api/maintenance'
import { shouldShowDialog } from '@/lib/utils/dialog-helpers'

export interface MaintenanceTask {
  id: string
  name: string
  taskName: string
  isDbTask?: boolean
  supportsDryRun?: boolean
}

export interface BackupCheck {
  canProceed: boolean
  blockingReason?: string | null
}

export interface TaskRunnerCallbacks {
  onTaskComplete?: () => void
  onShowDialog?: (config: {
    title: string
    description: string
    actionLabel: string
    onConfirm: () => void
    storageKey?: string
  }) => void
  onShowTaskResult?: (result: {
    taskName: string
    dryRun: boolean
    result: Record<string, unknown> | null
  }) => void
}

export function useMaintenanceTaskRunner(
  dryRun: boolean,
  backupCheck: BackupCheck | null,
  callbacks: TaskRunnerCallbacks = {},
) {
  const [triggeringTask, setTriggeringTask] = useState<string | null>(null)

  const handleFileCleanupTrigger = async (
    taskName: string,
    supportsDryRun: boolean = false,
  ) => {
    setTriggeringTask(taskName)
    const useDryRun = dryRun && supportsDryRun
    try {
      const result = await triggerMaintenanceTask(taskName, {
        dryRun: useDryRun,
        waitForResult: true,
        timeout: 60,
      })

      if (result.result) {
        callbacks.onShowTaskResult?.({
          taskName,
          dryRun: useDryRun,
          result: result.result as Record<string, unknown>,
        })
      }

      const isDry = useDryRun ? ' (dry run)' : ''
      if (result.status === 'completed') {
        toast.success(`${taskName}${isDry}: ${result.message}`)
      } else if (result.status === 'timeout') {
        toast.warning(`${taskName}${isDry}: Still running...`)
      } else {
        toast.success(result.message)
      }

      if (!useDryRun) {
        setTimeout(() => callbacks.onTaskComplete?.(), 2000)
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to trigger task'
      toast.error(`Failed to trigger ${taskName}: ${message}`)
    } finally {
      setTriggeringTask(null)
    }
  }

  const handleDatabaseTask = async (taskId: string) => {
    const config = DB_TASK_DIALOG_CONFIGS[taskId]
    const apiFunc = DB_TASK_API_FUNCTIONS[taskId]
    if (!config || !apiFunc) return

    setTriggeringTask(taskId)
    try {
      const result = await apiFunc(dryRun)
      const extracted = config.successExtractor(result)
      const action = dryRun ? 'would be processed' : 'processed'
      toast.success(`${config.title} ${result.status}: ${extracted} ${action}`)
      callbacks.onTaskComplete?.()
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed'
      toast.error(`${config.title} failed: ${message}`)
    } finally {
      setTriggeringTask(null)
    }
  }

  const triggerTask = (task: MaintenanceTask) => {
    const liveBlocked =
      !dryRun && backupCheck !== null && !backupCheck.canProceed

    if (liveBlocked && task.isDbTask) {
      toast.error(`Cannot run: ${backupCheck?.blockingReason}`)
      return
    }

    // Database tasks have special handlers with dialog config
    const dbConfig = DB_TASK_DIALOG_CONFIGS[task.id]
    if (dbConfig) {
      if (shouldShowDialog(dbConfig.storageKey, !dryRun)) {
        callbacks.onShowDialog?.({
          title: dbConfig.title,
          description: dryRun
            ? dbConfig.dryRunDescription
            : dbConfig.liveDescription,
          actionLabel: dryRun ? dbConfig.dryRunLabel : dbConfig.liveLabel,
          onConfirm: () => handleDatabaseTask(task.id),
          storageKey: dryRun ? dbConfig.storageKey : undefined,
        })
      } else {
        handleDatabaseTask(task.id)
      }
    } else {
      // Regular file/data cleanup tasks
      handleFileCleanupTrigger(task.taskName, task.supportsDryRun ?? false)
    }
  }

  return {
    triggeringTask,
    triggerTask,
    handleFileCleanupTrigger,
    handleDatabaseTask,
  }
}
