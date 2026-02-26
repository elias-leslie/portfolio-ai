'use client'

import { useMemo, useState } from 'react'
import type React from 'react'
import type {
  CacheStatusResponse,
  FileCleanupStatusResponse,
  LastRunSummary,
  MaintenanceResult,
} from '@/lib/api/maintenance'
import { useTableSort } from '@/lib/hooks/useTableSort'
import type { TaskCategory } from '@/lib/maintenance/formatters'
import {
  getTaskIcon,
  TASK_CONFIGS,
  type TaskConfig,
} from '../maintenanceTaskConfig'

// Unified task interface
export interface MaintenanceTask {
  id: string
  name: string
  category: TaskCategory
  icon: React.ReactNode
  sizeMb: number | null
  fileCount: number | null
  schedule: string
  retentionPolicy: string | null
  lastRun: MaintenanceResult | null
  path: string | null
  description: string | null
  taskName: string
  isDbTask?: boolean
  supportsDryRun?: boolean
}

// Sort configuration
export type SortKey =
  | 'name'
  | 'category'
  | 'sizeMb'
  | 'fileCount'
  | 'schedule'
  | 'lastRun'

function createTaskFromConfig(
  config: TaskConfig,
  fileCleanup: FileCleanupStatusResponse | null,
  cacheStatus: CacheStatusResponse | null,
  lastRunSummary: LastRunSummary | null,
): MaintenanceTask | null {
  const getLastRun = (taskName: string) =>
    lastRunSummary?.tasks?.[taskName] || null

  let sizeMb: number | null = null
  let fileCount: number | null = null
  let path: string | null = null
  let scheduleOverride: string | undefined
  let retentionOverride: string | undefined

  if (config.fileCleanupKey && fileCleanup) {
    const data = fileCleanup[config.fileCleanupKey]
    if (data) {
      sizeMb = data.sizeMb
      fileCount = data.fileCount
      path = data.path
      scheduleOverride = data.schedule
      retentionOverride = data.retentionPolicy
    }
  }

  if (config.id === 'dev_caches' && cacheStatus) {
    sizeMb = cacheStatus.totalSizeMb
    fileCount = cacheStatus.totalFileCount
  }

  if (config.fileCleanupKey && !fileCleanup) return null
  if (config.id === 'dev_caches' && !cacheStatus) return null

  const lastRun =
    getLastRun(config.taskName) ||
    (config.fallbackTaskName ? getLastRun(config.fallbackTaskName) : null)

  return {
    id: config.id,
    name: config.name,
    category: config.category,
    icon: getTaskIcon(config),
    sizeMb,
    fileCount,
    schedule: scheduleOverride || config.schedule,
    retentionPolicy: retentionOverride ?? config.retentionPolicy,
    lastRun,
    path,
    description: config.description,
    taskName: config.taskName,
    isDbTask: config.isDbTask,
    supportsDryRun: config.supportsDryRun,
  }
}

function sortTasks(
  tasks: MaintenanceTask[],
  sortKey: SortKey,
  sortDirection: 'asc' | 'desc',
): MaintenanceTask[] {
  return [...tasks].sort((a, b) => {
    let comparison = 0
    switch (sortKey) {
      case 'name':
        comparison = a.name.localeCompare(b.name)
        break
      case 'category':
        comparison = a.category.localeCompare(b.category)
        break
      case 'sizeMb':
        comparison = (a.sizeMb ?? -1) - (b.sizeMb ?? -1)
        break
      case 'fileCount':
        comparison = (a.fileCount ?? -1) - (b.fileCount ?? -1)
        break
      case 'schedule':
        comparison = a.schedule.localeCompare(b.schedule)
        break
      case 'lastRun': {
        const aTime = a.lastRun?.startedAt
          ? new Date(a.lastRun.startedAt).getTime()
          : 0
        const bTime = b.lastRun?.startedAt
          ? new Date(b.lastRun.startedAt).getTime()
          : 0
        comparison = aTime - bTime
        break
      }
    }
    return sortDirection === 'asc' ? comparison : -comparison
  })
}

interface UseMaintenanceTasksOptions {
  fileCleanup: FileCleanupStatusResponse | null
  cacheStatus: CacheStatusResponse | null
  lastRunSummary: LastRunSummary | null
}

export function useMaintenanceTasks({
  fileCleanup,
  cacheStatus,
  lastRunSummary,
}: UseMaintenanceTasksOptions) {
  const [categoryFilter, setCategoryFilter] = useState<TaskCategory | 'all'>(
    'all',
  )
  const { sortKey, sortDirection, toggleSort } = useTableSort<SortKey>('category')

  const tasks = useMemo(
    () =>
      TASK_CONFIGS.map((config) =>
        createTaskFromConfig(config, fileCleanup, cacheStatus, lastRunSummary),
      ).filter((task): task is MaintenanceTask => task !== null),
    [fileCleanup, cacheStatus, lastRunSummary],
  )

  const filteredTasks = useMemo(() => {
    const filtered =
      categoryFilter === 'all'
        ? tasks
        : tasks.filter((t) => t.category === categoryFilter)
    return sortTasks(filtered, sortKey, sortDirection)
  }, [tasks, categoryFilter, sortKey, sortDirection])

  return {
    tasks,
    filteredTasks,
    categoryFilter,
    setCategoryFilter,
    sortKey,
    sortDirection,
    toggleSort,
  }
}
