/**
 * Shared helpers and icons for ApiSourcesOverview sub-components
 */

import type { ReactElement } from 'react'
import {
  BarChart3,
  CheckCircle2,
  Cloud,
  Database,
  Newspaper,
  Zap,
} from 'lucide-react'

export interface ExpandedProviders {
  [key: string]: boolean
}

export const getCapabilityIcon = (cap: string): ReactElement => {
  switch (cap) {
    case 'ohlcv':
      return <BarChart3 className="h-3 w-3" />
    case 'fundamentals':
      return <Database className="h-3 w-3" />
    case 'news':
      return <Newspaper className="h-3 w-3" />
    case 'reference':
      return <Cloud className="h-3 w-3" />
    case 'economic_indicators':
      return <Zap className="h-3 w-3" />
    default:
      return <CheckCircle2 className="h-3 w-3" />
  }
}

export const getTierColor = (tier: string) => {
  return tier === 'FREE'
    ? 'bg-status-success/10 text-status-success border-status-success/20'
    : 'bg-accent/10 text-accent border-accent/20'
}

export const getPriorityBadge = (priority: number) => {
  if (priority === 1)
    return { label: 'Primary', color: 'bg-status-info/10 text-status-info' }
  if (priority <= 10)
    return {
      label: 'High',
      color: 'bg-status-success/10 text-status-success',
    }
  if (priority <= 20)
    return {
      label: 'Medium',
      color: 'bg-status-warning/10 text-status-warning',
    }
  return { label: 'Backup', color: 'bg-surface-muted text-text-muted' }
}

export const formatRateLimit = (limit: number | null, unit: string) => {
  if (limit === null) return 'Unlimited'
  return `${limit}/${unit}`
}
