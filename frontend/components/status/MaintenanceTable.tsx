'use client'

import { ArrowUpDown, Loader2, PlayCircle } from 'lucide-react'
import type React from 'react'
import { useMemo, useState } from 'react'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { MaintenanceResult } from '@/lib/api/maintenance'
import { useMaintenanceBackupCheck } from '@/lib/hooks/useMaintenanceBackupCheck'
import { useMaintenanceBatchRunner } from '@/lib/hooks/useMaintenanceBatchRunner'
import { useMaintenanceData } from '@/lib/hooks/useMaintenanceData'
import { useMaintenanceTaskRunner } from '@/lib/hooks/useMaintenanceTaskRunner'
import { useTableSort } from '@/lib/hooks/useTableSort'
import {
  formatLastRun,
  formatSize,
  getCategoryBadge,
  getStatusIcon,
  type TaskCategory,
} from '@/lib/maintenance/formatters'
import { useDialogState } from './hooks/useDialogState'
import { BatchResultsDialog, TaskResultDisplay } from './MaintenanceDialogs'
import { MaintenanceSummaryStats } from './MaintenanceSummaryStats'
import { MaintenanceTableToolbar } from './MaintenanceTableToolbar'
import {
  DB_TASK_API_FUNCTIONS,
  getTaskIcon,
  TASK_CONFIGS,
  type TaskConfig,
} from './maintenanceTaskConfig'
import { ServiceActionDialog } from './ServiceActionDialog'

// Unified task interface
interface MaintenanceTask {
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
  taskName: string // Celery task name
  isDbTask?: boolean // Database tasks need special handling
  supportsDryRun?: boolean // Only some tasks support dryRun
}

// Sort configuration
type SortKey =
  | 'name'
  | 'category'
  | 'sizeMb'
  | 'fileCount'
  | 'schedule'
  | 'lastRun'

export function MaintenanceTable() {
  // Use the maintenance data hook
  const {
    fileCleanup,
    lastRunSummary,
    diskSpace,
    dbSize,
    schedule,
    cacheStatus,
    isLoading,
    isRefreshing,
    refresh: fetchAllData,
  } = useMaintenanceData()

  // Additional local state
  const [dryRun, setDryRun] = useState(true)

  // Backup check hook
  const { backupCheck, isCheckingBackup } = useMaintenanceBackupCheck(dryRun)

  // Dialog state hook
  const {
    actionDialogOpen,
    actionDialogConfig,
    setActionDialogOpen,
    openActionDialog,
    taskResultOpen,
    taskResult,
    setTaskResultOpen,
    showTaskResult,
    batchResultsOpen,
    batchResults,
    setBatchResultsOpen,
    setBatchResults,
    isRunningAll,
    setIsRunningAll,
  } = useDialogState()

  // Task runner hook
  const { triggeringTask, triggerTask } = useMaintenanceTaskRunner(
    dryRun,
    backupCheck,
    {
      onTaskComplete: () => fetchAllData(),
      onShowDialog: openActionDialog,
      onShowTaskResult: showTaskResult,
    },
  )

  // Batch runner hook
  const { runAll, isRunning: _isRunningBatch } = useMaintenanceBatchRunner()

  const [categoryFilter, setCategoryFilter] = useState<TaskCategory | 'all'>(
    'all',
  )
  const { sortKey, sortDirection, toggleSort } =
    useTableSort<SortKey>('category')

  const handleRefresh = () => {
    fetchAllData()
  }

  // Build unified task list from config
  const tasks: MaintenanceTask[] = useMemo(() => {
    const getLastRun = (taskName: string) =>
      lastRunSummary?.tasks?.[taskName] || null

    // Factory function to create task from config
    const createTask = (config: TaskConfig): MaintenanceTask | null => {
      // Get file cleanup data if applicable
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

      // Get cache status data for dev_caches task
      if (config.id === 'dev_caches' && cacheStatus) {
        sizeMb = cacheStatus.totalSizeMb
        fileCount = cacheStatus.totalFileCount
      }

      // Skip file cleanup tasks if data not available
      if (config.fileCleanupKey && !fileCleanup) return null
      if (config.id === 'dev_caches' && !cacheStatus) return null

      // Get last run with fallback
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

    return TASK_CONFIGS.map(createTask).filter(
      (task): task is MaintenanceTask => task !== null,
    )
  }, [fileCleanup, cacheStatus, lastRunSummary])

  // Filter and sort tasks
  const filteredTasks = useMemo(() => {
    let result = [...tasks]

    // Apply category filter
    if (categoryFilter !== 'all') {
      result = result.filter((t) => t.category === categoryFilter)
    }

    // Apply sorting
    result.sort((a, b) => {
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

    return result
  }, [tasks, categoryFilter, sortKey, sortDirection])

  // Run all tasks and collect results using the batch runner hook
  const handleRunAll = async () => {
    setIsRunningAll(true)
    setBatchResults([])

    const results = await runAll(filteredTasks, dryRun, DB_TASK_API_FUNCTIONS)

    setIsRunningAll(false)
    setBatchResults(results)
    setBatchResultsOpen(true)

    // Refresh data after run (if not dry run)
    if (!dryRun) {
      setTimeout(fetchAllData, 2000)
    }
  }

  // Summary stats
  const getSummary = () => {
    if (isLoading) return 'Loading...'
    if (diskSpace?.alerts?.length)
      return `${diskSpace.alerts.length} disk alert(s)`
    return `${tasks.length} tasks ready`
  }

  // Calculate current task index for toolbar progress display
  const currentTaskIndex = filteredTasks.findIndex(
    (t) => t.taskName === triggeringTask,
  )

  // Block live mode if backup check failed
  const liveBlocked = !dryRun && backupCheck !== null && !backupCheck.canProceed

  return (
    <>
      <ExpandableCard
        title="Maintenance"
        description="System cleanup, database maintenance, and scheduled tasks"
        summary={getSummary()}
        defaultCollapsed
        actions={
          <MaintenanceTableToolbar
            dryRun={dryRun}
            setDryRun={setDryRun}
            isCheckingBackup={isCheckingBackup}
            backupCheck={backupCheck}
            isRunningAll={isRunningAll}
            isRefreshing={isRefreshing}
            filteredTaskCount={filteredTasks.length}
            currentTaskIndex={currentTaskIndex}
            onRunAll={handleRunAll}
            onRefresh={handleRefresh}
          />
        }
      >
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary Stats */}
            <MaintenanceSummaryStats
              filesSizeMb={fileCleanup?.totalSizeMb || 0}
              databaseSizeMb={dbSize?.databaseSizeMb || 0}
              cacheSizeMb={cacheStatus?.totalSizeMb || 0}
              diskUsedPercentage={
                diskSpace?.partitions?.[0]?.usedPercentage ?? null
              }
            />

            {/* Filter */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Filter:</span>
              <Select
                value={categoryFilter}
                onValueChange={(v) =>
                  setCategoryFilter(v as TaskCategory | 'all')
                }
              >
                <SelectTrigger className="w-32 h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All ({tasks.length})</SelectItem>
                  <SelectItem value="file">
                    File ({tasks.filter((t) => t.category === 'file').length})
                  </SelectItem>
                  <SelectItem value="cache">
                    Cache ({tasks.filter((t) => t.category === 'cache').length})
                  </SelectItem>
                  <SelectItem value="data">
                    Data ({tasks.filter((t) => t.category === 'data').length})
                  </SelectItem>
                  <SelectItem value="database">
                    Database (
                    {tasks.filter((t) => t.category === 'database').length})
                  </SelectItem>
                  <SelectItem value="system">
                    System (
                    {tasks.filter((t) => t.category === 'system').length})
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Table */}
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => toggleSort('name')}
                  >
                    <div className="flex items-center gap-1">
                      Task
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => toggleSort('category')}
                  >
                    <div className="flex items-center gap-1">
                      Category
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none text-right"
                    onClick={() => toggleSort('sizeMb')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Size
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none text-right"
                    onClick={() => toggleSort('fileCount')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Files
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead>Retention</TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => toggleSort('schedule')}
                  >
                    <div className="flex items-center gap-1">
                      Schedule
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => toggleSort('lastRun')}
                  >
                    <div className="flex items-center gap-1">
                      Last Run
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead className="w-12 text-center">Run</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTasks.map((task) => (
                  <TableRow key={task.id} className="group">
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {task.icon}
                        <span className="font-medium">{task.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>{getCategoryBadge(task.category)}</TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {formatSize(task.sizeMb)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {task.fileCount?.toLocaleString() ?? '—'}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {task.retentionPolicy ?? '—'}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {task.schedule}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        {getStatusIcon(task.lastRun)}
                        <span className="text-xs text-muted-foreground">
                          {formatLastRun(task.lastRun)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0"
                        onClick={() => triggerTask(task)}
                        disabled={
                          triggeringTask === task.taskName ||
                          (liveBlocked && task.isDbTask)
                        }
                        title={`Run ${task.name}`}
                      >
                        {triggeringTask === task.taskName ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <PlayCircle className="h-4 w-4" />
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* Scheduled Tasks Summary */}
            <div className="text-xs text-muted-foreground text-center pt-2 border-t">
              {schedule?.totalCount || 0} scheduled maintenance tasks configured
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
            {taskResult.result && (
              <TaskResultDisplay result={taskResult.result} />
            )}
          </div>
        </ServiceActionDialog>
      )}

      {/* Batch Results Dialog (Run All) */}
      <BatchResultsDialog
        open={batchResultsOpen}
        onOpenChange={setBatchResultsOpen}
        dryRun={dryRun}
        results={batchResults}
      />
    </>
  )
}
