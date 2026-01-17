/**
 * Hook for fetching system resources data
 */

import { useEffect, useState } from 'react'
import { getSystemResources, type SystemResources } from '../api/resources'

export function useSystemResources(refreshInterval: number = 5000) {
  const [resources, setResources] = useState<SystemResources | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchResources = async () => {
    try {
      const data = await getSystemResources()
      setResources(data)
      setError(null)
    } catch (err) {
      setError(err as Error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    // Fetch immediately
    fetchResources()

    // Set up interval for auto-refresh
    const interval = setInterval(fetchResources, refreshInterval)

    return () => clearInterval(interval)
  }, [refreshInterval, fetchResources])

  return { resources, isLoading, error, refresh: fetchResources }
}
