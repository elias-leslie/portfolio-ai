'use client'

import { useEffect, useState } from 'react'
import {
  type DetailedHealthResponse,
  fetchDetailedHealth,
} from '@/lib/api/status'
import { useNewsHealth } from '@/lib/hooks/useNewsHealth'
import { useStatusStream } from '@/lib/hooks/useStatusStream'
import { useSystemResources } from '@/lib/hooks/useSystemResources'
import { useSystemStatus } from '@/lib/hooks/useSystemStatus'

const REALTIME_STORAGE_KEY = 'status.realtimeEnabled'

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
    let cancelled = false
    const fetchDetailed = async () => {
      try {
        const data = await fetchDetailedHealth()
        if (!cancelled) setDetailedHealth(data)
      } catch (err) {
        console.error('Failed to fetch detailed health:', err)
      }
    }

    fetchDetailed()
    const interval = setInterval(fetchDetailed, 30000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

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
  }
}
