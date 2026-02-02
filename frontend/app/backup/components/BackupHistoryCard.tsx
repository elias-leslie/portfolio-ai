'use client'

import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
} from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  type BackupEntry,
  backupKeys,
  formatBackupAge,
  formatBytes,
  getBackupHistory,
} from '@/lib/api/backup'
import { cn } from '@/lib/utils'

export function BackupHistoryCard() {
  const { data: history, isLoading } = useQuery({
    queryKey: backupKeys.history(),
    queryFn: getBackupHistory,
    staleTime: 60_000, // 1 minute
  })

  const [expandedBackup, setExpandedBackup] = useState<string | null>(null)

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backup History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-text-muted" />
          </div>
        </CardContent>
      </Card>
    )
  }

  const backups = history?.backups || []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Backup History</span>
          <span className="text-sm font-normal text-text-muted">
            {backups.length} / {history?.retention || 30} max
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {backups.length === 0 ? (
          <div className="py-8 text-center text-text-muted">
            No backups yet. Click &quot;Full Backup&quot; to create your first
            backup.
          </div>
        ) : (
          <div className="space-y-2">
            {backups.slice(0, 10).map((backup: BackupEntry, index: number) => (
              <div
                key={backup.name}
                className={cn(
                  'rounded-md border border-border p-3 transition-colors',
                  expandedBackup === backup.name && 'bg-surface-muted',
                )}
              >
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() =>
                    setExpandedBackup(
                      expandedBackup === backup.name ? null : backup.name,
                    )
                  }
                >
                  <div className="flex items-center gap-2">
                    {expandedBackup === backup.name ? (
                      <ChevronDown className="size-4 text-text-muted" />
                    ) : (
                      <ChevronRight className="size-4 text-text-muted" />
                    )}
                    <span className="font-mono text-sm">{backup.name}</span>
                    {index === 0 && (
                      <Badge variant="success" className="text-xs">
                        Latest
                      </Badge>
                    )}
                    {backup.verification && (
                      <Badge
                        variant={
                          backup.verification.verified
                            ? 'success'
                            : 'destructive'
                        }
                        className="text-xs"
                      >
                        {backup.verification.verified ? (
                          <>
                            <CheckCircle2 className="mr-1 size-3" />
                            {backup.verification.totalFiles} files
                          </>
                        ) : (
                          <>
                            <AlertCircle className="mr-1 size-3" />
                            FAILED
                          </>
                        )}
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-text-muted">
                    <span>{formatBackupAge(backup.timestamp)}</span>
                    <span>{formatBytes(backup.sizeBytes)}</span>
                  </div>
                </div>

                {expandedBackup === backup.name && (
                  <div className="mt-3 space-y-3 border-t border-border pt-3">
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-text-muted">Timestamp:</span>{' '}
                        <span className="font-mono">
                          {new Date(backup.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-text-muted">Archive Size:</span>{' '}
                        <span>{formatBytes(backup.sizeBytes)}</span>
                      </div>
                      <div>
                        <span className="text-text-muted">DB Size:</span>{' '}
                        <span>{formatBytes(backup.dbSizeBytes)}</span>
                      </div>
                      <div>
                        <span className="text-text-muted">Status:</span>{' '}
                        <Badge
                          variant={
                            backup.status === 'ok' ? 'success' : 'destructive'
                          }
                          className="text-xs"
                        >
                          {backup.status}
                        </Badge>
                      </div>
                    </div>

                    {backup.verification && (
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-text-muted uppercase">
                          Verification Details
                        </div>

                        {backup.verification.errors.length > 0 && (
                          <div className="rounded-md border border-loss bg-loss/10 p-2 text-xs text-loss">
                            {backup.verification.errors.map((err, i) => (
                              <div key={i}>{err}</div>
                            ))}
                          </div>
                        )}

                        <div className="grid grid-cols-4 gap-2 text-xs rounded-md bg-surface-muted p-2">
                          {Object.entries(backup.verification.tree)
                            .sort(([, a], [, b]) => b.count - a.count)
                            .map(([path, entry]) => (
                              <div key={path} className="flex justify-between">
                                <span className="text-text-muted truncate">
                                  {path}
                                </span>
                                <span className="font-mono ml-1">
                                  {entry.count}
                                </span>
                              </div>
                            ))}
                        </div>

                        <div className="flex items-center gap-4 text-xs text-text-muted">
                          <span>
                            Total:{' '}
                            <span className="font-mono">
                              {backup.verification.totalFiles}
                            </span>{' '}
                            files
                          </span>
                          <span className="font-mono text-[10px] truncate">
                            {backup.verification.checksum}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {backups.length > 10 && (
              <div className="pt-2 text-center text-xs text-text-muted">
                Showing 10 of {backups.length} backups
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
