'use client'

import { AlertCircle, Calendar, CheckCircle2, Clock, Loader2, PlayCircle, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { MaintenanceResult } from '@/lib/api/maintenance'

// Unified maintenance item component for consistent display
interface MaintenanceItemProps {
  title: string
  icon: React.ReactNode
  metrics: { label: string; value: string }[]
  badge?: {
    text: string
    variant?: 'default' | 'secondary' | 'destructive' | 'outline'
  }
  schedule?: string
  lastRun?: MaintenanceResult | null
  onTrigger: () => void
  isTriggering: boolean
  disabled?: boolean
}

export function MaintenanceItem({
  title,
  icon,
  metrics,
  badge,
  schedule,
  lastRun,
  onTrigger,
  isTriggering,
  disabled,
}: MaintenanceItemProps) {
  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="h-3 w-3 text-status-success" />
      case 'error':
        return <AlertCircle className="h-3 w-3 text-status-error" />
      case 'running':
        return <RefreshCw className="h-3 w-3 animate-spin text-status-info" />
      default:
        return null
    }
  }

  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {icon}
          <span className="font-medium">{title}</span>
          {lastRun?.status && getStatusIcon(lastRun.status)}
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={onTrigger}
          disabled={isTriggering || disabled}
          title={`Run ${title} now`}
        >
          {isTriggering ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
        </Button>
      </div>

      <div className="space-y-2 text-sm">
        {metrics.map((metric, idx) => (
          <div key={idx} className="flex justify-between">
            <span className="text-muted-foreground">{metric.label}:</span>
            <span className="font-mono">{metric.value}</span>
          </div>
        ))}
        {badge && (
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Policy:</span>
            <Badge variant={badge.variant || 'secondary'} className="text-xs">
              {badge.text}
            </Badge>
          </div>
        )}
        {schedule && (
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Schedule:</span>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {schedule}
            </span>
          </div>
        )}
        {lastRun?.startedAt && (
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Last run:</span>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {new Date(lastRun.startedAt).toLocaleString()}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

// Section header component
export function SectionHeader({
  title,
  icon,
}: {
  title: string
  icon: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-2 mb-3 mt-6 first:mt-0">
      {icon}
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
        {title}
      </h3>
    </div>
  )
}
