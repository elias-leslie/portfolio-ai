'use client'

import { Activity, AlertCircle, CheckCircle2, RotateCw } from 'lucide-react'
import type { ReactElement } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ServiceStatus } from '@/lib/api/status'

interface ServiceCardProps {
  serviceName: string
  status: ServiceStatus
  onRestart?: (serviceName: string) => void
}

export function ServiceCard({
  serviceName,
  status,
  onRestart,
}: ServiceCardProps) {
  // Format uptime
  const formatUptime = (seconds?: number): string => {
    if (!seconds) return 'N/A'
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (hours > 0) {
      return `${hours}h ${minutes}m`
    }
    return `${minutes}m`
  }

  // Get status badge variant and icon
  const getStatusDisplay = (
    statusValue: string,
  ): {
    variant: 'default' | 'secondary' | 'destructive'
    icon: ReactElement
  } => {
    switch (statusValue) {
      case 'running':
        return {
          variant: 'default',
          icon: <CheckCircle2 className="h-4 w-4 text-gain" />,
        }
      case 'degraded':
        return {
          variant: 'secondary',
          icon: <AlertCircle className="h-4 w-4 text-warning" />,
        }
      case 'down':
        return {
          variant: 'destructive',
          icon: <AlertCircle className="h-4 w-4 text-loss" />,
        }
      default:
        return {
          variant: 'secondary',
          icon: <Activity className="h-4 w-4" />,
        }
    }
  }

  const { variant, icon } = getStatusDisplay(status.status)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            {icon}
            <span>{status.serviceName}</span>
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant={variant}>{status.status}</Badge>
            {onRestart && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onRestart(serviceName)}
                title={`Restart ${status.serviceName}`}
              >
                <RotateCw className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Process details */}
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-muted-foreground">PID</div>
            <div className="font-mono">{status.pid || 'N/A'}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Uptime</div>
            <div className="font-mono">
              {formatUptime(status.uptimeSeconds)}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground">Memory</div>
            <div className="font-mono">
              {status.memoryMb ? `${status.memoryMb} MB` : 'N/A'}
            </div>
          </div>
        </div>

        {/* Status message */}
        {status.message && (
          <div className="text-sm text-muted-foreground border-l-2 border-warning pl-3">
            {status.message}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
