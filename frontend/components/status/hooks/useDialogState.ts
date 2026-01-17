'use client'

import { useCallback, useState } from 'react'
import type { BatchResult } from '../MaintenanceDialogs'

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

export interface DialogState {
  // Action dialog
  actionDialogOpen: boolean
  actionDialogConfig: ActionDialogConfig | null
  setActionDialogOpen: (open: boolean) => void
  openActionDialog: (config: ActionDialogConfig) => void

  // Task result dialog
  taskResultOpen: boolean
  taskResult: TaskResultData | null
  setTaskResultOpen: (open: boolean) => void
  showTaskResult: (result: TaskResultData) => void

  // Batch results dialog
  batchResultsOpen: boolean
  batchResults: BatchResult[]
  setBatchResultsOpen: (open: boolean) => void
  setBatchResults: (results: BatchResult[]) => void

  // Running state
  isRunningAll: boolean
  setIsRunningAll: (running: boolean) => void
}

export function useDialogState(): DialogState {
  // Action dialog state
  const [actionDialogOpen, setActionDialogOpen] = useState(false)
  const [actionDialogConfig, setActionDialogConfig] =
    useState<ActionDialogConfig | null>(null)

  // Task result dialog state
  const [taskResultOpen, setTaskResultOpen] = useState(false)
  const [taskResult, setTaskResult] = useState<TaskResultData | null>(null)

  // Batch results dialog state
  const [batchResultsOpen, setBatchResultsOpen] = useState(false)
  const [batchResults, setBatchResults] = useState<BatchResult[]>([])

  // Running state
  const [isRunningAll, setIsRunningAll] = useState(false)

  const openActionDialog = useCallback((config: ActionDialogConfig) => {
    setActionDialogConfig(config)
    setActionDialogOpen(true)
  }, [])

  const showTaskResult = useCallback((result: TaskResultData) => {
    setTaskResult(result)
    setTaskResultOpen(true)
  }, [])

  return {
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
  }
}
