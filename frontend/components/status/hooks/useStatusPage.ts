'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { restartService } from '@/lib/api/service-control'
import {
  type DetailedHealthResponse,
  fetchDetailedHealth,
} from '@/lib/api/status'
import { useNewsHealth } from '@/lib/hooks/useNewsHealth'
import { useStatusStream } from '@/lib/hooks/useStatusStream'
import { useSystemResources } from '@/lib/hooks/useSystemResources'
import { useSystemStatus } from '@/lib/hooks/useSystemStatus'
import { shouldShowDialog } from '@/lib/utils/dialog-helpers'

const REALTIME_STORAGE_KEY = 'status.realtimeEnabled'

export interface ActionDialogConfig {
  title: string
  description: string
  actionLabel: string
  onConfirm: () => void
  storageKey?: string
}

export function useStatusPage() {
  const [realtimeEnabled, setRealtimeEnabled] = useState(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem(REALTIME_STORAGE_KEY) === 'true'
  })

  useEffect(() => {
    localStorage.setItem(REALTIME_STORAGE_KEY, String(realtimeEnabled))
  }, [realtimeEnabled])

  const {
    status: streamStatus,
    connectionState,
    isLoading: streamLoading,
    error: streamError,
    retryConnection,
  } = useStatusStream()

  const {
    data: pollingStatus,
    isLoading: pollingLoading,
    error: pollingError,
  } = useSystemStatus()

  const health = realtimeEnabled ? streamStatus : pollingStatus
  const isLoading = realtimeEnabled ? streamLoading : pollingLoading
  const error = realtimeEnabled ? streamError : pollingError

  const [lastUpdateTimestamp, setLastUpdateTimestamp] = useState<number | null>(null)
  const [isDataStale, setIsDataStale] = useState(false)

  const resourcesInterval = realtimeEnabled ? 5000 : 30000
  const { resources, isLoading: resourcesLoading } = useSystemResources(resourcesInterval)

  const {
    data: newsHealth,
    isLoading: newsHealthLoading,
    error: newsHealthError,
    refresh: refreshNewsHealth,
  } = useNewsHealth(60000)

  const [detailedHealth, setDetailedHealth] = useState<DetailedHealthResponse | null>(null)

  useEffect(() => {
    const fetchDetailed = async () => {
      try {
        const data = await fetchDetailedHealth()
        setDetailedHealth(data)
      } catch (err) {
        console.error('Failed to fetch detailed health:', err)
      }
    }

    fetchDetailed()
    const interval = setInterval(fetchDetailed, 30000)
    return () => clearInterval(interval)
  }, [])

  const [actionDialogOpen, setActionDialogOpen] = useState(false)
  const [actionDialogConfig, setActionDialogConfig] = useState<ActionDialogConfig | null>(null)
  const [isActionLoading, setIsActionLoading] = useState(false)

  useEffect(() => {
    if (!health) return
    setLastUpdateTimestamp(Date.now())
  }, [health])

  useEffect(() => {
    if (lastUpdateTimestamp === null) return
    setIsDataStale(false)
    const timeout = window.setTimeout(() => setIsDataStale(true), 10000)
    return () => window.clearTimeout(timeout)
  }, [lastUpdateTimestamp])

  const handleRestartService = async (serviceName: string) => {
    setIsActionLoading(true)
    try {
      const result = await restartService(serviceName)
      toast.success(result.message ?? `${serviceName} restart requested`)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to restart service'
      toast.error(`Failed to restart ${serviceName}: ${message}`)
      throw err instanceof Error ? err : new Error(message)
    } finally {
      setIsActionLoading(false)
    }
  }

  const triggerRestartService = (serviceName: string) => {
    const storageKey = `status.confirm.restart.${serviceName}`
    if (shouldShowDialog(storageKey)) {
      setActionDialogConfig({
        title: `Restart ${serviceName}`,
        description: `This will restart the ${serviceName} service. The service will be briefly unavailable during the restart.`,
        actionLabel: 'Restart Service',
        onConfirm: () => handleRestartService(serviceName),
        storageKey,
      })
      setActionDialogOpen(true)
    } else {
      handleRestartService(serviceName)
    }
  }

  return {
    realtimeEnabled,
    setRealtimeEnabled,
    connectionState,
    retryConnection,
    health,
    isLoading,
    error,
    isDataStale,
    resources,
    resourcesLoading,
    newsHealth,
    newsHealthLoading,
    newsHealthError,
    refreshNewsHealth,
    detailedHealth,
    actionDialogOpen,
    setActionDialogOpen,
    actionDialogConfig,
    isActionLoading,
    triggerRestartService,
  }
}
