'use client'

import { Loader2 } from 'lucide-react'
import { useState } from 'react'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import { useMaintenanceBackupCheck } from '@/lib/hooks/useMaintenanceBackupCheck'
import { useMaintenanceBatchRunner } from '@/lib/hooks/useMaintenanceBatchRunner'
import { useMaintenanceData } from '@/lib/hooks/useMaintenanceData'
import { useMaintenanceTaskRunner } from '@/lib/hooks/useMaintenanceTaskRunner'
import { useDialogState } from './hooks/useDialogState'
import { useMaintenanceTasks } from './hooks/useMaintenanceTasks'
import { DB_TASK_API_FUNCTIONS } from './maintenanceTaskConfig'
import { MaintenanceResultDialogs } from './MaintenanceResultDialogs'
import { MaintenanceSummaryStats } from './MaintenanceSummaryStats'
import { MaintenanceTableToolbar } from './MaintenanceTableToolbar'
import { MaintenanceTasksTable } from './MaintenanceTasksTable'

export function MaintenanceTable() {
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

  const [dryRun, setDryRun] = useState(true)

  const { backupCheck, isCheckingBackup } = useMaintenanceBackupCheck(dryRun)

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

  const { triggeringTask, triggerTask } = useMaintenanceTaskRunner(
    dryRun,
    backupCheck,
    {
      onTaskComplete: () => fetchAllData(),
      onShowDialog: openActionDialog,
      onShowTaskResult: showTaskResult,
    },
  )

  const { runAll } = useMaintenanceBatchRunner()

  const {
    tasks,
    filteredTasks,
    categoryFilter,
    setCategoryFilter,
    toggleSort,
  } = useMaintenanceTasks({
    fileCleanup,
    cacheStatus,
    lastRunSummary,
  })

  const handleRefresh = () => fetchAllData()

  const handleRunAll = async () => {
    setIsRunningAll(true)
    setBatchResults([])
    const results = await runAll(filteredTasks, dryRun, DB_TASK_API_FUNCTIONS)
    setIsRunningAll(false)
    setBatchResults(results)
    setBatchResultsOpen(true)
    if (!dryRun) {
      setTimeout(fetchAllData, 2000)
    }
  }

  const getSummary = () => {
    if (isLoading) return 'Loading...'
    if (diskSpace?.alerts?.length)
      return `${diskSpace.alerts.length} disk alert(s)`
    return `${tasks.length} tasks ready`
  }

  const currentTaskIndex = filteredTasks.findIndex(
    (t) => t.taskName === triggeringTask,
  )

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
            <MaintenanceSummaryStats
              filesSizeMb={fileCleanup?.totalSizeMb || 0}
              databaseSizeMb={dbSize?.databaseSizeMb || 0}
              cacheSizeMb={cacheStatus?.totalSizeMb || 0}
              diskUsedPercentage={
                diskSpace?.partitions?.[0]?.usedPercentage ?? null
              }
            />
            <MaintenanceTasksTable
              tasks={tasks}
              filteredTasks={filteredTasks}
              categoryFilter={categoryFilter}
              setCategoryFilter={setCategoryFilter}
              toggleSort={toggleSort}
              triggeringTask={triggeringTask}
              liveBlocked={liveBlocked}
              scheduledTaskCount={schedule?.totalCount || 0}
              onTriggerTask={triggerTask}
            />
          </div>
        )}
      </ExpandableCard>

      <MaintenanceResultDialogs
        actionDialogOpen={actionDialogOpen}
        actionDialogConfig={actionDialogConfig}
        setActionDialogOpen={setActionDialogOpen}
        taskResultOpen={taskResultOpen}
        taskResult={taskResult}
        setTaskResultOpen={setTaskResultOpen}
        batchResultsOpen={batchResultsOpen}
        batchResults={batchResults}
        setBatchResultsOpen={setBatchResultsOpen}
        dryRun={dryRun}
      />
    </>
  )
}
