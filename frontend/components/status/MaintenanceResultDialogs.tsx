'use client'

import {
  BatchResultsDialog,
  type BatchResult,
  TaskResultDisplay,
} from './MaintenanceDialogs'
import { ServiceActionDialog } from './ServiceActionDialog'

interface ActionDialogConfig {
  title: string
  description: string
  actionLabel: string
  onConfirm: () => void
  storageKey?: string
}

interface TaskResultData {
  taskName: string
  dryRun: boolean
  result: Record<string, unknown> | null
}

interface MaintenanceResultDialogsProps {
  // Action confirmation dialog
  actionDialogOpen: boolean
  actionDialogConfig: ActionDialogConfig | null
  setActionDialogOpen: (open: boolean) => void

  // Task result dialog
  taskResultOpen: boolean
  taskResult: TaskResultData | null
  setTaskResultOpen: (open: boolean) => void

  // Batch results dialog
  batchResultsOpen: boolean
  batchResults: BatchResult[]
  setBatchResultsOpen: (open: boolean) => void
  dryRun: boolean
}

export function MaintenanceResultDialogs({
  actionDialogOpen,
  actionDialogConfig,
  setActionDialogOpen,
  taskResultOpen,
  taskResult,
  setTaskResultOpen,
  batchResultsOpen,
  batchResults,
  setBatchResultsOpen,
  dryRun,
}: MaintenanceResultDialogsProps) {
  return (
    <>
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
