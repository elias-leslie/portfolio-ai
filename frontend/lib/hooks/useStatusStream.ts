/**
 * React hook for Server-Sent Events (SSE) status streaming with automatic fallback to polling
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { HealthResponse } from '../api/status'
import { useSystemStatus } from './useSystemStatus'
import { buildApiUrl } from '../api-config'

type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'fallback'

interface UseStatusStreamResult {
  status: HealthResponse | undefined
  connectionState: ConnectionState
  error: Error | null
  isLoading: boolean
  retryConnection: () => void
}

const MAX_FAILURES = 3

/**
 * Hook to stream real-time status updates via Server-Sent Events
 *
 * Automatically falls back to polling after 3 failed connection attempts.
 * Provides manual retry function to attempt SSE reconnection from fallback mode.
 */
export function useStatusStream(): UseStatusStreamResult {
  const [status, setStatus] = useState<HealthResponse | undefined>()
  // Internal state excludes "fallback" - that's derived from useFallback
  const [internalConnectionState, setInternalConnectionState] =
    useState<Exclude<ConnectionState, 'fallback'>>('connecting')
  const [error, setError] = useState<Error | null>(null)
  const [failCount, setFailCount] = useState(0)
  const [useFallback, setUseFallback] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)

  // Derive connectionState from useFallback (avoids setState-in-effect)
  const connectionState: ConnectionState = useFallback
    ? 'fallback'
    : internalConnectionState

  // Fallback polling (only used when SSE fails)
  const pollingData = useSystemStatus()

  // Cleanup function
  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [])

  // Retry connection (resets fail count and attempts SSE again)
  const retryConnection = useCallback(() => {
    setFailCount(0)
    setUseFallback(false)
    setInternalConnectionState('connecting')
    setError(null)
  }, [])

  // Setup EventSource connection
  useEffect(() => {
    // Don't connect if we're in fallback mode
    if (useFallback) {
      return
    }

    // Create EventSource
    const sseUrl = buildApiUrl('/api/status/stream')
    const eventSource = new EventSource(sseUrl)
    eventSourceRef.current = eventSource

    // Connection opened
    eventSource.onopen = () => {
      setInternalConnectionState('connected')
      setError(null)
      setFailCount(0) // Reset fail count on successful connection
    }

    // Message received
    eventSource.onmessage = (event) => {
      try {
        const data: HealthResponse = JSON.parse(event.data)
        setStatus(data)
      } catch (err) {
        console.error('Failed to parse SSE message:', err)
        setError(err instanceof Error ? err : new Error('Parse error'))
      }
    }

    // Error occurred
    eventSource.onerror = () => {
      setInternalConnectionState('disconnected')
      const newFailCount = failCount + 1
      setFailCount(newFailCount)

      // After MAX_FAILURES, switch to fallback
      if (newFailCount >= MAX_FAILURES) {
        setUseFallback(true)
        // connectionState is derived from useFallback
        cleanup()
      } else {
        // EventSource will automatically retry
        setInternalConnectionState('connecting')
      }
    }

    // Cleanup on unmount
    return cleanup
  }, [useFallback, failCount, cleanup])

  return {
    status: useFallback ? pollingData.data : status,
    connectionState,
    error: error || (useFallback ? (pollingData.error as Error | null) : null),
    isLoading:
      connectionState === 'connecting' ||
      (useFallback && pollingData.isLoading),
    retryConnection,
  }
}
