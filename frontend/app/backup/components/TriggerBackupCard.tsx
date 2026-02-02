'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ChevronDown,
  ChevronRight,
  HardDrive,
  Loader2,
  RefreshCw,
  Terminal,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  type BackupJobStatus,
  backupKeys,
  getBackupJobStatus,
  triggerBackup,
} from '@/lib/api/backup'
import { cn } from '@/lib/utils'

export function TriggerBackupCard() {
  const queryClient = useQueryClient()
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [showOutput, setShowOutput] = useState(false)

  const triggerMutation = useMutation({
    mutationFn: (quick: boolean) => triggerBackup(quick),
    onSuccess: (data) => {
      if (data.status === 'started') {
        setActiveJobId(data.jobId)
        toast.success('Backup started', { description: data.message })
      } else {
        toast.info('Backup already running', { description: data.message })
        setActiveJobId(data.jobId)
      }
    },
    onError: (error) => {
      toast.error('Failed to trigger backup', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  // Poll job status when we have an active job
  const { data: jobStatus } = useQuery({
    queryKey: backupKeys.job(activeJobId || ''),
    queryFn: () => getBackupJobStatus(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const data = query.state.data as BackupJobStatus | undefined
      // Stop polling when job is complete
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false
      }
      return 2000 // Poll every 2 seconds while running
    },
  })

  // Handle job completion
  useEffect(() => {
    if (jobStatus?.status === 'completed') {
      toast.success('Backup completed successfully!')
      queryClient.invalidateQueries({ queryKey: backupKeys.status() })
      queryClient.invalidateQueries({ queryKey: backupKeys.history() })
    } else if (jobStatus?.status === 'failed') {
      toast.error('Backup failed', {
        description: jobStatus.error || 'Unknown error',
      })
    }
  }, [jobStatus?.status, queryClient, jobStatus?.error])

  const isRunning = triggerMutation.isPending || jobStatus?.status === 'running'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <RefreshCw className={cn('size-5', isRunning && 'animate-spin')} />
          Trigger Backup
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Button
            onClick={() => triggerMutation.mutate(false)}
            disabled={isRunning}
          >
            {isRunning ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <HardDrive className="mr-2 size-4" />
                Full Backup
              </>
            )}
          </Button>
          <Button
            variant="outline"
            onClick={() => triggerMutation.mutate(true)}
            disabled={isRunning}
          >
            Quick Backup
          </Button>
        </div>

        <p className="text-xs text-text-muted">
          <strong>Full Backup:</strong> Creates fresh PostgreSQL dump + archives
          all project data.
          <br />
          <strong>Quick Backup:</strong> Uses existing daily DB dump (faster,
          for checkpoints).
        </p>

        {jobStatus && activeJobId && (
          <div className="rounded-md border border-border bg-surface-muted p-3 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge
                  variant={
                    jobStatus.status === 'completed'
                      ? 'success'
                      : jobStatus.status === 'failed'
                        ? 'destructive'
                        : 'secondary'
                  }
                >
                  {jobStatus.status.toUpperCase()}
                </Badge>
                <span className="text-xs text-text-muted font-mono">
                  Job: {activeJobId}
                </span>
              </div>
              {jobStatus.output && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowOutput(!showOutput)}
                >
                  {showOutput ? (
                    <ChevronDown className="size-4" />
                  ) : (
                    <ChevronRight className="size-4" />
                  )}
                  <Terminal className="ml-1 size-4" />
                </Button>
              )}
            </div>

            {showOutput && jobStatus.output && (
              <pre className="max-h-48 overflow-auto rounded bg-bg p-2 text-xs font-mono">
                {jobStatus.output}
              </pre>
            )}

            {jobStatus.error && (
              <div className="text-xs text-loss">{jobStatus.error}</div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
