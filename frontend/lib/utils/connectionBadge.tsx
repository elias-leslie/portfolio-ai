/**
 * Connection badge and banner utilities for status page
 * Extracted from status/page.tsx for reusability
 */

import { Clock3, Radio, RefreshCw, Wifi, WifiOff } from 'lucide-react'
import type React from 'react'

export type ConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'fallback'

export interface ConnectionBadgeConfig {
  icon: React.ReactNode
  text: string
  variant: 'default' | 'secondary' | 'destructive'
}

export interface ConnectionBannerConfig {
  tone: 'danger' | 'warning'
  title: string
  description: string
  icon: React.ReactNode
}

/**
 * Get connection badge configuration based on state
 */
export function getConnectionBadge(
  connectionState: ConnectionState,
  realtimeEnabled: boolean,
): ConnectionBadgeConfig {
  if (!realtimeEnabled) {
    return {
      icon: <RefreshCw className="h-3 w-3" />,
      text: 'Polling',
      variant: 'secondary',
    }
  }

  switch (connectionState) {
    case 'connected':
      return {
        icon: <Wifi className="h-3 w-3" />,
        text: 'Live',
        variant: 'default',
      }
    case 'connecting':
      return {
        icon: <Radio className="h-3 w-3 animate-pulse" />,
        text: 'Connecting',
        variant: 'secondary',
      }
    case 'disconnected':
      return {
        icon: <WifiOff className="h-3 w-3" />,
        text: 'Disconnected',
        variant: 'destructive',
      }
    case 'fallback':
      return {
        icon: <RefreshCw className="h-3 w-3" />,
        text: 'Polling',
        variant: 'secondary',
      }
  }
}

/**
 * Get connection banner configuration for warning/error states
 * Returns null if no banner should be shown
 */
export function getConnectionBanner(
  connectionState: ConnectionState,
  realtimeEnabled: boolean,
  isDataStale: boolean,
): ConnectionBannerConfig | null {
  if (!realtimeEnabled) return null

  if (connectionState === 'disconnected') {
    return {
      tone: 'danger',
      title: 'Live stream disconnected',
      description:
        'We lost connection to the SSE stream. Reconnect to resume real-time updates.',
      icon: <WifiOff className="h-4 w-4 text-loss" />,
    }
  }

  if (connectionState === 'fallback') {
    return {
      tone: 'warning',
      title: 'Live stream unavailable',
      description:
        'Showing backup polling data (30s interval). Retry the live stream for lower latency.',
      icon: <Radio className="h-4 w-4 text-accent" />,
    }
  }

  if (connectionState === 'connected' && isDataStale) {
    return {
      tone: 'warning',
      title: 'No live events detected',
      description:
        "We haven't received new status events for 10 seconds. Refresh the stream to ensure accuracy.",
      icon: <Clock3 className="h-4 w-4 text-accent" />,
    }
  }

  return null
}
