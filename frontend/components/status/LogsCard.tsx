'use client'

import { useQuery } from '@tanstack/react-query'
import { FileText } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import {
  fetchUnifiedLogs,
  type UnifiedLogsResponse,
} from '@/lib/api/status'
import { LogsCardAlerts } from './LogsCardAlerts'
import { LogsCardFilters } from './LogsCardFilters'
import { LogsCardLogList } from './LogsCardLogList'
import { formatTimestamp, SERVICE_DISPLAY_NAMES } from './LogsCard.types'

export function LogsCard({ readOnly = false }: { readOnly?: boolean }) {
  const [levelFilter, setLevelFilter] = useState<string | undefined>(undefined)
  const [serviceFilter, setServiceFilter] = useState<string | undefined>(undefined)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [copied, setCopied] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState<number>(30000)
  const [timeRange, setTimeRange] = useState<string>('5 minutes ago')

  const { data, error, isLoading } = useQuery<UnifiedLogsResponse>({
    queryKey: ['unified-logs', levelFilter, serviceFilter, timeRange],
    queryFn: () =>
      fetchUnifiedLogs({
        lines: 500,
        since: timeRange,
        level: levelFilter && levelFilter !== 'ALL' ? levelFilter : undefined,
        service:
          serviceFilter && serviceFilter !== 'ALL' ? serviceFilter : undefined,
      }),
    refetchInterval: refreshInterval || false,
    refetchOnWindowFocus: false,
    staleTime: 0,
  })

  const logs = data?.logs
  const sortedLogs = useMemo(() => {
    if (!logs) return []
    return [...logs].toSorted((a, b) => {
      const timeA = new Date(a.timestamp).getTime()
      const timeB = new Date(b.timestamp).getTime()
      return sortOrder === 'asc' ? timeA - timeB : timeB - timeA
    })
  }, [logs, sortOrder])

  const logCounts = useMemo(
    () =>
      data?.levelCounts || {
        CRITICAL: 0,
        ERROR: 0,
        WARN: 0,
        INFO: 0,
        DEBUG: 0,
        UNKNOWN: 0,
      },
    [data?.levelCounts],
  )

  const totalUnfilteredCount = useMemo(
    () =>
      (logCounts.CRITICAL || 0) +
      (logCounts.ERROR || 0) +
      (logCounts.WARN || 0) +
      (logCounts.INFO || 0) +
      (logCounts.DEBUG || 0) +
      (logCounts.UNKNOWN || 0),
    [logCounts],
  )

  const serviceCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    data?.logs.forEach((log) => {
      counts[log.service] = (counts[log.service] || 0) + 1
    })
    return counts
  }, [data?.logs])

  const handleCopy = async () => {
    const text = sortedLogs
      .map(
        (log) =>
          `[${formatTimestamp(log.timestamp)}] [${SERVICE_DISPLAY_NAMES[log.service] || log.service}] [${log.level}] ${log.message}`,
      )
      .join('\n')
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const summary = [
    `${sortedLogs.length} entries`,
    readOnly ? 'Read only' : 'Live',
    serviceFilter ? SERVICE_DISPLAY_NAMES[serviceFilter] : 'All services',
  ]
    .filter(Boolean)
    .join(' • ')

  return (
    <ExpandableCard
      title={
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          <span>Service Logs</span>
        </div>
      }
      description="Recent read-only logs with filtering for quick diagnosis."
      summary={summary}
      defaultCollapsed
    >
      <div className="space-y-4">
        <LogsCardFilters
          serviceFilter={serviceFilter}
          levelFilter={levelFilter}
          timeRange={timeRange}
          refreshInterval={refreshInterval}
          sortOrder={sortOrder}
          copied={copied}
          totalUnfilteredCount={totalUnfilteredCount}
          logCounts={logCounts}
          serviceCounts={serviceCounts}
          sortedLogsLength={sortedLogs.length}
          onServiceFilterChange={setServiceFilter}
          onLevelFilterChange={setLevelFilter}
          onTimeRangeChange={setTimeRange}
          onRefreshIntervalChange={setRefreshInterval}
          onToggleSortOrder={() =>
            setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
          }
          onCopy={handleCopy}
        />

        <LogsCardAlerts
          restartRequired={false}
          restartPending={false}
          error={error}
          onRestartServices={() => {}}
        />

        <LogsCardLogList
          isLoading={isLoading}
          sortedLogs={sortedLogs}
          levelFilter={levelFilter}
          serviceFilter={serviceFilter}
        />
      </div>
    </ExpandableCard>
  )
}
