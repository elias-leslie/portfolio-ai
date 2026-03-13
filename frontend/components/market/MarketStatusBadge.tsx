'use client'

import { Clock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useMarketStatus } from '@/lib/hooks/useMarketIntelligence'
import { cn } from '@/lib/utils'

const STATUS_CONFIG = {
  open: {
    label: 'Market Open',
    dotColor: 'bg-gain',
    badgeVariant: 'default' as const,
  },
  pre_market: {
    label: 'Pre-Market',
    dotColor: 'bg-warning',
    badgeVariant: 'secondary' as const,
  },
  after_hours: {
    label: 'After Hours',
    dotColor: 'bg-warning',
    badgeVariant: 'secondary' as const,
  },
  closed: {
    label: 'Market Closed',
    dotColor: 'bg-text-muted',
    badgeVariant: 'secondary' as const,
  },
}

export function MarketStatusBadge() {
  const { data, isLoading, error } = useMarketStatus()

  if (isLoading) {
    return (
      <Badge variant="secondary" className="gap-1.5 px-2 py-1">
        <Clock className="size-3 animate-pulse" />
        <span className="hidden sm:inline">Loading...</span>
      </Badge>
    )
  }

  if (error || !data) {
    return (
      <Badge variant="secondary" className="gap-1.5 px-2 py-1">
        <div className="size-2 rounded-full bg-text-muted" />
        <span className="hidden sm:inline">Status unavailable</span>
      </Badge>
    )
  }

  const config = STATUS_CONFIG[data.status]

  // Build tooltip content
  const tooltipLines: string[] = []
  tooltipLines.push(`Current: ${data.currentTimeEt}`)
  tooltipLines.push(`Last Trading: ${data.lastTradingDay}`)
  tooltipLines.push(`Next Trading: ${data.nextTradingDay}`)
  if (data.isHoliday && data.holidayName) {
    tooltipLines.push(`Holiday: ${data.holidayName}`)
  }
  if (data.isEarlyClose && data.earlyCloseName) {
    tooltipLines.push(`Early Close: ${data.earlyCloseName}`)
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant={config.badgeVariant}
            className="cursor-help gap-1.5 px-2 py-1"
          >
            <div
              className={cn(
                'size-2 rounded-full',
                config.dotColor,
                data.status === 'open' && 'animate-pulse',
              )}
            />
            <span className="hidden sm:inline">{config.label}</span>
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <div className="space-y-1 text-xs">
            {tooltipLines.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
