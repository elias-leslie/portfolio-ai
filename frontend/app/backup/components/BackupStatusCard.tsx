'use client'

import { useQuery } from '@tanstack/react-query'
import { HardDrive, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  backupKeys,
  formatBackupAge,
  formatBytes,
  getBackupStatus,
  getStatusColor,
} from '@/lib/api/backup'
import { cn } from '@/lib/utils'

import { StatusIcon } from './StatusIcon'

export function BackupStatusCard() {
  const {
    data: status,
    isLoading,
    error,
  } = useQuery({
    queryKey: backupKeys.status(),
    queryFn: getBackupStatus,
    staleTime: 30_000, // 30 seconds
    refetchInterval: 60_000, // 1 minute
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="size-5" />
            Backup Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-text-muted" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error || !status) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="size-5" />
            Backup Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border border-loss bg-loss/10 p-4 text-sm text-loss">
            Failed to load backup status: {error?.message || 'Unknown error'}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <StatusIcon status={status.status} />
          Backup Status
          <Badge
            variant={
              status.status === 'healthy'
                ? 'success'
                : status.status === 'stale'
                  ? 'warning'
                  : 'destructive'
            }
            className="ml-auto"
          >
            {status.status.toUpperCase()}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className={cn('text-sm', getStatusColor(status.status))}>
          {status.message}
        </p>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-text-muted">Total Backups:</span>{' '}
            <span className="font-medium">{status.backupCount}</span>
          </div>
          <div>
            <span className="text-text-muted">Destination:</span>{' '}
            <span className="font-mono text-xs">{status.destination}</span>
          </div>
        </div>

        {status.latestBackup && (
          <div className="rounded-md bg-surface-muted p-3">
            <div className="text-xs text-text-muted uppercase mb-1">
              Latest Backup
            </div>
            <div className="font-mono text-sm">{status.latestBackup.name}</div>
            <div className="flex gap-4 mt-1 text-xs text-text-muted">
              <span>{formatBackupAge(status.latestBackup.timestamp)}</span>
              <span>{formatBytes(status.latestBackup.sizeBytes)}</span>
              <span>DB: {formatBytes(status.latestBackup.dbSizeBytes)}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
