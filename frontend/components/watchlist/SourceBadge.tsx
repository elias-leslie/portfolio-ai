/**
 * SourceBadge component displays the data source for price information
 * with color coding based on source priority and stale status.
 */

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface SourceBadgeProps {
  source: string
  stale?: boolean
  priority?: number
  className?: string
}

export function SourceBadge({
  source,
  stale = false,
  priority,
  className,
}: SourceBadgeProps) {
  // Determine variant based on source priority and stale status
  const getVariant = ():
    | 'default'
    | 'outline'
    | 'secondary'
    | 'gain'
    | 'loss'
    | 'neutral'
    | 'viz-0'
    | 'viz-1'
    | 'viz-2'
    | 'viz-3'
    | 'viz-4'
    | 'viz-5'
    | null
    | undefined => {
    if (stale) return 'loss' // Red for stale data

    // Source priority: lower = better (yfinance = 1, alphavantage = 6)
    if (priority === 1 || source.toLowerCase() === 'yfinance') {
      return 'gain' // Green for primary source
    }

    return 'secondary' // Gray for backup sources
  }

  // Format source name for display
  const formatSourceName = (name: string): string => {
    const nameMap: Record<string, string> = {
      yfinance: 'YFinance',
      twelvedata: 'TwelveData',
      fmp: 'FMP',
      polygon: 'Polygon',
      finnhub: 'Finnhub',
      alphavantage: 'AlphaVantage',
    }

    return nameMap[name.toLowerCase()] || name
  }

  return (
    <Badge
      variant={getVariant()}
      className={cn('text-[10px] font-normal', className)}
    >
      {formatSourceName(source)}
    </Badge>
  )
}
