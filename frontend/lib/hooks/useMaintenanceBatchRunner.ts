'use client'

import { useCallback, useState } from 'react'
import type { BatchResult } from '@/components/status/MaintenanceDialogs'
import {
  type MaintenanceResult,
  triggerMaintenanceTask,
} from '@/lib/api/maintenance'

export interface MaintenanceTask {
  id: string
  name: string
  taskName: string
  supportsDryRun?: boolean
  isDbTask?: boolean
}

export interface UseMaintenanceBatchRunnerReturn {
  runAll: (
    tasks: MaintenanceTask[],
    dryRun: boolean,
    dbTaskApiFunctions: Record<
      string,
      (dryRun: boolean) => Promise<MaintenanceResult>
    >,
  ) => Promise<BatchResult[]>
  isRunning: boolean
  currentTask: string | null
  batchResults: BatchResult[]
}

/**
 * Hook to run all maintenance tasks in sequence and collect results.
 * Supports both regular Celery tasks and database tasks with custom API functions.
 *
 * @returns {UseMaintenanceBatchRunnerReturn} runAll function, loading state, and results
 */
export function useMaintenanceBatchRunner(): UseMaintenanceBatchRunnerReturn {
  const [isRunning, setIsRunning] = useState(false)
  const [currentTask, setCurrentTask] = useState<string | null>(null)
  const [batchResults, setBatchResults] = useState<BatchResult[]>([])

  const runAll = useCallback(
    async (
      tasks: MaintenanceTask[],
      dryRun: boolean,
      dbTaskApiFunctions: Record<
        string,
        (dryRun: boolean) => Promise<MaintenanceResult>
      >,
    ): Promise<BatchResult[]> => {
      setIsRunning(true)
      setBatchResults([])
      const results: BatchResult[] = []

      for (const task of tasks) {
        // In dry run mode, SKIP tasks that don't support dryRun
        if (dryRun && !task.supportsDryRun) {
          results.push({
            taskName: task.name,
            taskId: task.taskName,
            status: 'success',
            result: {
              skipped: true,
              reason: 'Task does not support dry run preview',
            },
          })
          continue
        }

        setCurrentTask(task.taskName)

        try {
          let taskResult: Record<string, unknown> | null = null

          // Handle DB tasks via config-driven API lookup
          const apiFunc = dbTaskApiFunctions[task.id]
          if (apiFunc) {
            const r = await apiFunc(dryRun)
            taskResult = { ...r, ...r.summary }
          } else {
            // Regular Celery tasks
            const result = await triggerMaintenanceTask(task.taskName, {
              dryRun: dryRun,
              waitForResult: true,
              timeout: 60,
            })
            taskResult = result.result as Record<string, unknown> | null
          }

          results.push({
            taskName: task.name,
            taskId: task.taskName,
            status: 'success',
            result: taskResult,
          })
        } catch (error) {
          results.push({
            taskName: task.name,
            taskId: task.taskName,
            status: 'error',
            result: null,
            error: error instanceof Error ? error.message : 'Unknown error',
          })
        }
      }

      setCurrentTask(null)
      setIsRunning(false)
      setBatchResults(results)

      return results
    },
    [],
  )

  return {
    runAll,
    isRunning,
    currentTask,
    batchResults,
  }
}
