/**
 * React hook for Server-Sent Events (SSE) status streaming with automatic fallback to polling
 */

import { useState, useEffect, useCallback, useRef } from "react";
import type { HealthResponse } from "../api/status";
import { useSystemStatus } from "./useSystemStatus";

type ConnectionState = "connecting" | "connected" | "disconnected" | "fallback";

interface UseStatusStreamResult {
  status: HealthResponse | undefined;
  connectionState: ConnectionState;
  error: Error | null;
  isLoading: boolean;
  retryConnection: () => void;
}

const MAX_FAILURES = 3;
const SSE_URL = `${process.env.NEXT_PUBLIC_API_URL || ""}/api/status/stream`;

/**
 * Hook to stream real-time status updates via Server-Sent Events
 *
 * Automatically falls back to polling after 3 failed connection attempts.
 * Provides manual retry function to attempt SSE reconnection from fallback mode.
 */
export function useStatusStream(): UseStatusStreamResult {
  const [status, setStatus] = useState<HealthResponse | undefined>();
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [error, setError] = useState<Error | null>(null);
  const [failCount, setFailCount] = useState(0);
  const [useFallback, setUseFallback] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Fallback polling (only used when SSE fails)
  // Note: pollingData.data is returned directly when useFallback is true (line 114)
  const pollingData = useSystemStatus();

  // Cleanup function
  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // Retry connection (resets fail count and attempts SSE again)
  const retryConnection = useCallback(() => {
    setFailCount(0);
    setUseFallback(false);
    setConnectionState("connecting");
    setError(null);
  }, []);

  // Sync connection state with fallback mode
  useEffect(() => {
    if (useFallback) {
      setConnectionState("fallback");
    }
  }, [useFallback]);

  // Setup EventSource connection
  useEffect(() => {
    // Don't connect if we're in fallback mode
    if (useFallback) {
      return;
    }

    // Create EventSource
    const eventSource = new EventSource(SSE_URL);
    eventSourceRef.current = eventSource;

    // Connection opened
    eventSource.onopen = () => {
      setConnectionState("connected");
      setError(null);
      setFailCount(0); // Reset fail count on successful connection
    };

    // Message received
    eventSource.onmessage = (event) => {
      try {
        const data: HealthResponse = JSON.parse(event.data);
        setStatus(data);
      } catch (err) {
        console.error("Failed to parse SSE message:", err);
        setError(err instanceof Error ? err : new Error("Parse error"));
      }
    };

    // Error occurred
    eventSource.onerror = () => {
      setConnectionState("disconnected");
      const newFailCount = failCount + 1;
      setFailCount(newFailCount);

      // After MAX_FAILURES, switch to fallback
      if (newFailCount >= MAX_FAILURES) {
        setUseFallback(true);
        // Note: connectionState will be set to "fallback" by the sync effect
        cleanup();
      } else {
        // EventSource will automatically retry
        setConnectionState("connecting");
      }
    };

    // Cleanup on unmount
    return cleanup;
  }, [useFallback, failCount, cleanup]);

  return {
    status: useFallback ? pollingData.data : status,
    connectionState,
    error: error || (useFallback ? pollingData.error as Error | null : null),
    isLoading: connectionState === "connecting" || (useFallback && pollingData.isLoading),
    retryConnection,
  };
}
