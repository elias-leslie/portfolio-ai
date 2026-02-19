'use client'

import { RefreshCw } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { UnifiedLogsResponse } from '@/lib/api/status'
import { formatTimestamp, getLevelColor, SERVICE_DISPLAY_NAMES } from './LogsCard.types'

type LogEntry = UnifiedLogsResponse['logs'][number]

interface LogsCardLogListProps {
  isLoading: boolean
  sortedLogs: LogEntry[]
  levelFilter: string | undefined
  serviceFilter: string | undefined
}

export function LogsCardLogList({
  isLoading,
  sortedLogs,
  levelFilter,
  serviceFilter,
}: LogsCardLogListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading logs...</span>
      </div>
    )
  }

  return (
    <ScrollArea className="h-[600px] w-full rounded-md border bg-bg p-4">
      {sortedLogs.length === 0 ? (
        <div className="text-sm text-muted-foreground text-center py-8">
          {levelFilter || serviceFilter
            ? 'No logs match the selected filters'
            : 'No logs available'}
        </div>
      ) : (
        <div className="space-y-1">
          {sortedLogs.map((log, idx) => (
            <div
              key={idx}
              className={`font-mono text-xs ${getLevelColor(log.level)}`}
            >
              <div>
                <span className="text-text-muted">
                  [{formatTimestamp(log.timestamp)}]
                </span>{' '}
                <span className="text-text-muted/70">
                  [{SERVICE_DISPLAY_NAMES[log.service] || log.service}]
                </span>{' '}
                <span className={getLevelColor(log.level)}>
                  [{log.level}]
                </span>
              </div>
              <pre className="whitespace-pre-wrap break-words ml-4 mt-0.5">
                {log.message}
              </pre>
            </div>
          ))}
        </div>
      )}
    </ScrollArea>
  )
}
