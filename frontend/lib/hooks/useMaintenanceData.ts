'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  type CacheStatusResponse,
  type DatabaseSizeResponse,
  type DiskSpaceResponse,
  type FileCleanupStatusResponse,
  getCacheStatus,
  getFileCleanupStatus,
  getMaintenanceDatabaseSize,
  getMaintenanceDiskSpace,
  getMaintenanceLastRun,
  getMaintenanceSchedule,
  type LastRunSummary,
  type MaintenanceScheduleResponse,
} from '@/lib/api/maintenance'

export interface MaintenanceDataState {
  fileCleanup: FileCleanupStatusResponse | null
  lastRunSummary: LastRunSummary | null
  diskSpace: DiskSpaceResponse | null
  dbSize: DatabaseSizeResponse | null
  schedule: MaintenanceScheduleResponse | null
  cacheStatus: CacheStatusResponse | null
  isLoading: boolean
  isRefreshing: boolean
}

export interface UseMaintenanceDataReturn extends MaintenanceDataState {
  refresh: () => Promise<void>
}

/**
 * Hook to fetch and manage maintenance data from multiple API endpoints.
 * Fetches file cleanup status, last run summary, disk space, database size,
 * schedule, and cache status in parallel.
 */
export function useMaintenanceData(): UseMaintenanceDataReturn {
  const [fileCleanup, setFileCleanup] =
    useState<FileCleanupStatusResponse | null>(null)
  const [lastRunSummary, setLastRunSummary] = useState<LastRunSummary | null>(
    null,
  )
  const [diskSpace, setDiskSpace] = useState<DiskSpaceResponse | null>(null)
  const [dbSize, setDbSize] = useState<DatabaseSizeResponse | null>(null)
  const [schedule, setSchedule] = useState<MaintenanceScheduleResponse | null>(
    null,
  )
  const [cacheStatus, setCacheStatus] = useState<CacheStatusResponse | null>(
    null,
  )
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const fetchAllData = useCallback(async () => {
    try {
      const [fileData, lastRun, diskData, dbData, scheduleData, cacheData] =
        await Promise.all([
          getFileCleanupStatus(),
          getMaintenanceLastRun(),
          getMaintenanceDiskSpace(),
          getMaintenanceDatabaseSize(),
          getMaintenanceSchedule(),
          getCacheStatus(),
        ])
      setFileCleanup(fileData)
      setLastRunSummary(lastRun)
      setDiskSpace(diskData)
      setDbSize(dbData)
      setSchedule(scheduleData)
      setCacheStatus(cacheData)
    } catch (error) {
      console.error('Failed to fetch maintenance data:', error)
      toast.error('Failed to load maintenance data')
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchAllData()
  }, [fetchAllData])

  const refresh = useCallback(async () => {
    setIsRefreshing(true)
    await fetchAllData()
  }, [fetchAllData])

  return {
    fileCleanup,
    lastRunSummary,
    diskSpace,
    dbSize,
    schedule,
    cacheStatus,
    isLoading,
    isRefreshing,
    refresh,
  }
}
