'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import {
  fetchLogLevelConfig,
  fetchUnifiedLogs,
  type LogLevelConfig,
  restartAllServices,
  setLogLevel,
  type UnifiedLogsResponse,
} from '@/lib/api/status'
import { LogsCardAlerts } from './LogsCardAlerts'
import { LogsCardFilters } from './LogsCardFilters'
import { LogsCardLogList } from './LogsCardLogList'
import { formatTimestamp, SERVICE_DISPLAY_NAMES } from './LogsCard.types'

export function LogsCard() {
  const queryClient = useQueryClient()
  const [levelFilter, setLevelFilter] = useState<string | undefined>(undefined)
  const [serviceFilter, setServiceFilter] = useState<string | undefined>(undefined)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [copied, setCopied] = useState(false)
  const [restartRequired, setRestartRequired] = useState(false)
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

  const { data: logLevelConfig } = useQuery<LogLevelConfig>({
    queryKey: ['log-level-config'],
    queryFn: fetchLogLevelConfig,
    refetchInterval: false,
    staleTime: 60000,
  })

  const logLevelMutation = useMutation({
    mutationFn: setLogLevel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['log-level-config'] })
      setRestartRequired(true)
    },
    onError: (error) => {
      toast.error(
        `Failed to change log level: ${
          error instanceof Error ? error.message : 'Unknown error'
        }`,
      )
    },
  })

  const restartMutation = useMutation({
    mutationFn: restartAllServices,
    onSuccess: () => {
      setRestartRequired(false)
      queryClient.invalidateQueries({ queryKey: ['log-level-config'] })
      toast.success('Services restarted successfully!')
    },
    onError: (error) => {
      toast.error(
        `Failed to restart services: ${
          error instanceof Error ? error.message : 'Unknown error'
        }`,
      )
    },
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

  const handleLogLevelChange = (newLevel: string) => {
    if (logLevelMutation.isPending) return
    logLevelMutation.mutate(newLevel)
  }

  const handleRestartServices = () => {
    if (restartMutation.isPending) return
    restartMutation.mutate()
  }

  const summary = [
    `${sortedLogs.length} entries`,
    `Level ${logLevelConfig?.currentLevel ?? 'INFO'}`,
    serviceFilter ? SERVICE_DISPLAY_NAMES[serviceFilter] : 'All services',
  ]
    .filter(Boolean)
    .join(' • ')

  return (
    <ExpandableCard
      title={
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          <span>Unified Logging</span>
        </div>
      }
      description="Live log stream with filtering, log-level control, and restart tooling."
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
          logLevelConfig={logLevelConfig}
          logLevelPending={logLevelMutation.isPending}
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
          onLogLevelChange={handleLogLevelChange}
        />

        <LogsCardAlerts
          restartRequired={restartRequired}
          restartPending={restartMutation.isPending}
          error={error}
          onRestartServices={handleRestartServices}
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
