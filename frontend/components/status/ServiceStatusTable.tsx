'use client'

import {
  AlertCircle,
  CheckCircle2,
  RotateCw,
  Server,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { ServiceStatus } from '@/lib/api/status'

interface ServiceStatusTableProps {
  services: Record<string, ServiceStatus>
  onRestart?: (serviceName: string) => void
  isRestartDisabled?: boolean
}

export function ServiceStatusTable({
  services,
  onRestart,
  isRestartDisabled,
}: ServiceStatusTableProps) {
  const serviceEntries = Object.entries(services)

  if (serviceEntries.length === 0) {
    return (
      <div className="text-center py-4 text-muted-foreground text-sm">
        No services found
      </div>
    )
  }

  const formatUptime = (seconds?: number): string => {
    if (!seconds) return '—'
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (days > 0) return `${days}d ${hours}h`
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m`
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <CheckCircle2 className="h-4 w-4 text-status-success" />
      case 'degraded':
        return <AlertCircle className="h-4 w-4 text-status-warning" />
      case 'down':
        return <XCircle className="h-4 w-4 text-status-error" />
      default:
        return <Server className="h-4 w-4 text-muted-foreground" />
    }
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive'> = {
      running: 'default',
      degraded: 'secondary',
      down: 'destructive',
    }
    const colors: Record<string, string> = {
      running: 'bg-status-success',
      degraded: 'bg-status-warning',
      down: 'bg-status-error',
    }
    return (
      <Badge
        variant={variants[status] || 'secondary'}
        className={colors[status] || ''}
      >
        {status}
      </Badge>
    )
  }

  // Summary counts
  const runningCount = serviceEntries.filter(
    ([, s]) => s.status === 'running',
  ).length
  const degradedCount = serviceEntries.filter(
    ([, s]) => s.status === 'degraded',
  ).length
  const downCount = serviceEntries.filter(([, s]) => s.status === 'down').length

  return (
    <div className="space-y-3">
      {/* Summary row */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-muted-foreground">Services:</span>
        <span className="flex items-center gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5 text-status-success" />
          {runningCount} running
        </span>
        {degradedCount > 0 && (
          <span className="flex items-center gap-1.5">
            <AlertCircle className="h-3.5 w-3.5 text-status-warning" />
            {degradedCount} degraded
          </span>
        )}
        {downCount > 0 && (
          <span className="flex items-center gap-1.5">
            <XCircle className="h-3.5 w-3.5 text-status-error" />
            {downCount} down
          </span>
        )}
      </div>

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[200px]">Service</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">PID</TableHead>
            <TableHead className="text-right">Memory</TableHead>
            <TableHead className="text-right">Uptime</TableHead>
            <TableHead>Message</TableHead>
            {onRestart && (
              <TableHead className="w-12 text-center">Action</TableHead>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {serviceEntries.map(([serviceName, status]) => (
            <TableRow key={serviceName} className="group">
              <TableCell>
                <div className="flex items-center gap-2">
                  {getStatusIcon(status.status)}
                  <span className="font-medium">{status.serviceName}</span>
                </div>
              </TableCell>
              <TableCell>{getStatusBadge(status.status)}</TableCell>
              <TableCell className="text-right font-mono text-xs text-muted-foreground">
                {status.pid || '—'}
              </TableCell>
              <TableCell className="text-right font-mono text-xs">
                {status.memoryMb ? `${status.memoryMb} MB` : '—'}
              </TableCell>
              <TableCell className="text-right font-mono text-xs">
                {formatUptime(status.uptimeSeconds)}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                {status.message || '—'}
              </TableCell>
              {onRestart && (
                <TableCell className="text-center">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => onRestart(serviceName)}
                    disabled={isRestartDisabled}
                    title={`Restart ${status.serviceName}`}
                  >
                    <RotateCw className="h-4 w-4" />
                  </Button>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
