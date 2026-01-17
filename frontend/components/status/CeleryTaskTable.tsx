'use client'

import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react'
import React, { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { TaskInfo } from '@/lib/api/celery'
import { useCeleryTasks } from '@/lib/hooks/useCeleryTasks'

export function CeleryTaskTable() {
  const [filter, setFilter] = useState<
    'all' | 'active' | 'pending' | 'completed' | 'failed'
  >('all')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  const { data, refetch, isLoading, isFetching } = useCeleryTasks(filter)

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedRows(newExpanded)
  }

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'ACTIVE':
        return (
          <Badge className="bg-status-info text-text-inverted animate-pulse">
            Active
          </Badge>
        )
      case 'PENDING':
        return (
          <Badge
            variant="secondary"
            className="bg-status-warning text-text-inverted"
          >
            Pending
          </Badge>
        )
      case 'SUCCESS':
        return (
          <Badge
            variant="default"
            className="bg-status-success text-text-inverted"
          >
            Completed
          </Badge>
        )
      case 'FAILURE':
        return <Badge variant="destructive">Failed</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return '-'
    if (seconds < 60) return `${seconds.toFixed(1)}s`
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}m ${secs}s`
  }

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return '-'
    try {
      const date = new Date(timestamp)
      return date.toLocaleString()
    } catch {
      return timestamp
    }
  }

  const getTaskDescription = (taskName: string): string => {
    // Map task names to human-readable descriptions
    const taskDescriptions: Record<string, string> = {
      // Watchlist tasks
      'app.tasks.watchlistTasks.refresh_watchlist_scores_task':
        'Refresh Watchlist Scores',
      refresh_watchlist_scores_task: 'Refresh Watchlist Scores',

      // Agent tasks
      'app.tasks.agentTasks.run_discovery_agent': 'Run Discovery Agent',
      'app.tasks.agentTasks.run_portfolio_analyzer': 'Run Portfolio Analyzer',
      run_discovery_agent: 'Run Discovery Agent',
      run_portfolio_analyzer: 'Run Portfolio Analyzer',

      // Data ingestion tasks
      'app.tasks.dataIngestionTasks.refresh_daily_ohlcv':
        'Refresh Daily Price Data (OHLCV)',
      'app.tasks.dataIngestionTasks.ingest_historical_ohlcv':
        'Ingest Historical Price Data',
      refresh_daily_ohlcv: 'Refresh Daily Price Data (OHLCV)',
      ingest_historical_ohlcv: 'Ingest Historical Price Data',

      // Indicator tasks
      'app.tasks.indicatorTasks.update_technical_indicators':
        'Update Technical Indicators',
      update_technical_indicators: 'Update Technical Indicators',

      // Fear & Greed tasks
      'app.tasks.fearGreedTasks.compute_fear_greed_daily':
        'Compute Fear & Greed Index',
      compute_fear_greed_daily: 'Compute Fear & Greed Index',

      // Paper trading tasks
      'app.tasks.update_paper_trades_task': 'Update Paper Trades',
      update_paper_trades_task: 'Update Paper Trades',
    }

    return taskDescriptions[taskName] || taskName.split('.').pop() || taskName
  }

  return (
    <div className="space-y-4">
      {/* Header with filter and refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h3 className="text-lg font-semibold">Celery Tasks</h3>
          {data && (
            <div className="text-sm text-muted-foreground">
              {data.total} total ({data.activeCount} active, {data.pendingCount}{' '}
              pending)
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={filter}
            onValueChange={(v) => setFilter(v as typeof filter)}
          >
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Tasks</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading || isFetching}
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      {/* Task table */}
      {!data && !isLoading ? (
        <div className="text-center py-8 text-muted-foreground">
          Click Refresh to load Celery tasks
        </div>
      ) : isLoading ? (
        <div className="text-center py-8 text-muted-foreground">
          Loading tasks...
        </div>
      ) : data && data.tasks.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          No tasks found
        </div>
      ) : data ? (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40px]"></TableHead>
                <TableHead className="w-[120px]">Status</TableHead>
                <TableHead>Task Description</TableHead>
                <TableHead className="w-[180px]">Started/Completed</TableHead>
                <TableHead className="w-[100px]">Duration</TableHead>
                <TableHead className="w-[150px]">Worker</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.tasks.map((task: TaskInfo) => (
                <React.Fragment key={task.id}>
                  <TableRow className="cursor-pointer hover:bg-muted/50">
                    <TableCell onClick={() => toggleRow(task.id)}>
                      {expandedRows.has(task.id) ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </TableCell>
                    <TableCell>{getStatusBadge(task.status)}</TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="font-medium">
                          {getTaskDescription(task.name)}
                        </div>
                        <div className="text-xs text-muted-foreground font-mono">
                          {task.name}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {formatTimestamp(task.startedAt || task.dateDone)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {task.status === 'ACTIVE' && task.duration ? (
                        <span className="text-status-info font-medium animate-pulse">
                          {formatDuration(task.duration)}
                        </span>
                      ) : (
                        formatDuration(task.duration)
                      )}
                    </TableCell>
                    <TableCell className="text-sm">
                      {task.worker ? (
                        <span className="font-mono text-xs">
                          {task.worker.split('@')[0]}
                        </span>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                  </TableRow>
                  {expandedRows.has(task.id) && (
                    <TableRow key={`${task.id}-details`}>
                      <TableCell colSpan={6} className="bg-muted/20">
                        <div className="p-4 space-y-3 text-sm">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <span className="font-semibold text-muted-foreground uppercase text-xs">
                                Task ID
                              </span>
                              <p className="font-mono text-xs mt-1">
                                {task.id}
                              </p>
                            </div>
                            <div>
                              <span className="font-semibold text-muted-foreground uppercase text-xs">
                                Full Task Name
                              </span>
                              <p className="font-mono text-xs mt-1">
                                {task.name}
                              </p>
                            </div>
                          </div>
                          {task.args &&
                            task.args !== '[]' &&
                            task.args !== '()' && (
                              <div>
                                <span className="font-semibold text-muted-foreground uppercase text-xs">
                                  Arguments
                                </span>
                                <pre className="bg-muted p-2 rounded mt-1 overflow-x-auto text-xs font-mono">
                                  {task.args}
                                </pre>
                              </div>
                            )}
                          {task.kwargs && task.kwargs !== '{}' && (
                            <div>
                              <span className="font-semibold text-muted-foreground uppercase text-xs">
                                Keyword Arguments
                              </span>
                              <pre className="bg-muted p-2 rounded mt-1 overflow-x-auto text-xs font-mono">
                                {task.kwargs}
                              </pre>
                            </div>
                          )}
                          {task.result && (
                            <div>
                              <span className="font-semibold text-status-success uppercase text-xs">
                                Result
                              </span>
                              <pre className="bg-status-success/10 border border-status-success/20 p-2 rounded mt-1 overflow-x-auto text-xs font-mono text-foreground">
                                {task.result}
                              </pre>
                            </div>
                          )}
                          {task.traceback && (
                            <div>
                              <span className="font-semibold text-destructive uppercase text-xs">
                                Error Traceback
                              </span>
                              <pre className="bg-destructive/10 border border-destructive/20 p-2 rounded mt-1 overflow-x-auto text-xs font-mono text-destructive">
                                {task.traceback}
                              </pre>
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </div>
  )
}
