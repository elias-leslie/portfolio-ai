'use client'

import { ArrowUpDown, Check, Copy } from 'lucide-react'
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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { SERVICE_DISPLAY_NAMES } from './LogsCard.types'

interface LogsCardFiltersProps {
  serviceFilter: string | undefined
  levelFilter: string | undefined
  timeRange: string
  refreshInterval: number
  sortOrder: 'asc' | 'desc'
  copied: boolean
  totalUnfilteredCount: number
  logCounts: Record<string, number>
  serviceCounts: Record<string, number>
  sortedLogsLength: number
  onServiceFilterChange: (val: string | undefined) => void
  onLevelFilterChange: (val: string | undefined) => void
  onTimeRangeChange: (val: string) => void
  onRefreshIntervalChange: (val: number) => void
  onToggleSortOrder: () => void
  onCopy: () => void
}

export function LogsCardFilters({
  serviceFilter,
  levelFilter,
  timeRange,
  refreshInterval,
  sortOrder,
  copied,
  totalUnfilteredCount,
  logCounts,
  serviceCounts,
  sortedLogsLength,
  onServiceFilterChange,
  onLevelFilterChange,
  onTimeRangeChange,
  onRefreshIntervalChange,
  onToggleSortOrder,
  onCopy,
}: LogsCardFiltersProps) {
  return (
    <TooltipProvider>
      <div className="flex flex-wrap items-center gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="inline-block">
              <Select
                value={serviceFilter || 'ALL'}
                onValueChange={(val) =>
                  onServiceFilterChange(val === 'ALL' ? undefined : val)
                }
              >
                <SelectTrigger className="h-8 min-w-[150px]">
                  <SelectValue placeholder="All Services" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">
                    All Services ({totalUnfilteredCount})
                  </SelectItem>
                  {Object.entries(SERVICE_DISPLAY_NAMES).map(([key, name]) => (
                    <SelectItem key={key} value={key}>
                      {name} ({serviceCounts[key] || 0})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p>Filter logs by specific service (for example Backend or Hatchet Worker)</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <div className="inline-block">
              <Select
                value={levelFilter || 'ALL'}
                onValueChange={(val) =>
                  onLevelFilterChange(val === 'ALL' ? undefined : val)
                }
              >
                <SelectTrigger className="h-8 min-w-[130px]">
                  <SelectValue placeholder="All Levels" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">
                    All Levels ({totalUnfilteredCount})
                  </SelectItem>
                  <SelectItem value="CRITICAL">
                    Critical ({logCounts.CRITICAL || 0})
                  </SelectItem>
                  <SelectItem value="ERROR">
                    Error ({logCounts.ERROR || 0})
                  </SelectItem>
                  <SelectItem value="WARN">
                    Warning ({logCounts.WARN || 0})
                  </SelectItem>
                  <SelectItem value="INFO">
                    Info ({logCounts.INFO || 0})
                  </SelectItem>
                  <SelectItem value="DEBUG">
                    Debug ({logCounts.DEBUG || 0})
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p>Filter logs by severity level</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <div className="inline-block">
              <Select value={timeRange} onValueChange={onTimeRangeChange}>
                <SelectTrigger className="h-8 min-w-[140px]">
                  <SelectValue placeholder="Time Range" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1 minute ago">Last 1 min</SelectItem>
                  <SelectItem value="5 minutes ago">Last 5 min</SelectItem>
                  <SelectItem value="15 minutes ago">Last 15 min</SelectItem>
                  <SelectItem value="1 hour ago">Last 1 hour</SelectItem>
                  <SelectItem value="24 hours ago">Last 24 hours</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p>Select the time window for fetching logs</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <div className="inline-block">
              <Select
                value={refreshInterval.toString()}
                onValueChange={(val) =>
                  onRefreshIntervalChange(parseInt(val, 10))
                }
              >
                <SelectTrigger className="h-8 min-w-[110px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1000">1s</SelectItem>
                  <SelectItem value="5000">5s</SelectItem>
                  <SelectItem value="15000">15s</SelectItem>
                  <SelectItem value="30000">30s</SelectItem>
                  <SelectItem value="60000">60s</SelectItem>
                  <SelectItem value="0">Off</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p>Set the auto-refresh interval</p>
          </TooltipContent>
        </Tooltip>

        <Badge variant="outline" className="shrink-0">
          {sortedLogsLength}
        </Badge>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              onClick={onToggleSortOrder}
              className="shrink-0"
            >
              <ArrowUpDown className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>
              Toggle sort order (
              {sortOrder === 'asc' ? 'Oldest First' : 'Newest First'})
            </p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              onClick={onCopy}
              className="shrink-0"
            >
              {copied ? (
                <Check className="h-4 w-4" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Copy visible logs to clipboard</p>
          </TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  )
}
