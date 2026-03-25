'use client'

import { Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { useMarketStatus } from '@/lib/hooks/useMarketIntelligence'
import { checkDataFreshness, cn, formatDate } from '@/lib/utils'
import { SECTOR_COLORS } from './sector-colors'

interface SectorInfo {
  symbol: string
  name: string
  price: number | null
  changePct: number | null
}

interface SectorMoversTableProps {
  leading: SectorInfo[]
  neutral: SectorInfo[]
  lagging: SectorInfo[]
  lastUpdated?: string
}

type SectorWithStatus = SectorInfo & {
  status: 'leading' | 'neutral' | 'lagging'
}

export function SectorMoversTable({
  leading,
  neutral,
  lagging,
  lastUpdated,
}: SectorMoversTableProps) {
  const { data: marketStatus } = useMarketStatus()

  // Combine and sort all sectors by changePct descending
  const allSectors: SectorWithStatus[] = [
    ...leading.map((s) => ({ ...s, status: 'leading' as const })),
    ...neutral.map((s) => ({ ...s, status: 'neutral' as const })),
    ...lagging.map((s) => ({ ...s, status: 'lagging' as const })),
  ].sort((a, b) => (b.changePct ?? 0) - (a.changePct ?? 0))

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'leading':
        return <TrendingUp className="h-4 w-4 text-gain" />
      case 'lagging':
        return <TrendingDown className="h-4 w-4 text-loss" />
      default:
        return <Minus className="h-4 w-4 text-text-muted" />
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-display italic text-lg tracking-tight text-text">Sector Movers</h3>
        <div className="flex gap-2 text-xs text-text-muted">
          <span className="flex items-center gap-1">
            <TrendingUp className="h-3 w-3 text-gain" />
            {leading.length}
          </span>
          <span className="flex items-center gap-1">
            <Minus className="h-3 w-3" />
            {neutral.length}
          </span>
          <span className="flex items-center gap-1">
            <TrendingDown className="h-3 w-3 text-loss" />
            {lagging.length}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-text-muted border-b border-border/50">
              <th className="text-left py-2 font-medium">Sector</th>
              <th className="text-right py-2 font-medium">Change</th>
              <th className="text-center py-2 font-medium w-10">Status</th>
            </tr>
          </thead>
          <tbody>
            {allSectors.map((sector) => (
              <tr
                key={sector.symbol}
                className="border-b border-border/30 hover:bg-surface-muted/50 transition-colors"
              >
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{
                        backgroundColor: SECTOR_COLORS[sector.symbol] || 'var(--color-neutral)',
                      }}
                    />
                    <span className="font-medium text-text">{sector.name}</span>
                  </div>
                </td>
                <td
                  className={cn(
                    'text-right py-2 font-semibold tabular-nums',
                    (sector.changePct ?? 0) >= 0 ? 'text-gain' : 'text-loss',
                  )}
                >
                  {(sector.changePct ?? 0) >= 0 ? '+' : ''}
                  {(sector.changePct ?? 0).toFixed(2)}%
                </td>
                <td className="text-center py-2">
                  {getStatusIcon(sector.status)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {lastUpdated &&
        (() => {
          const dataDate = lastUpdated.split('T')[0]
          const freshness = checkDataFreshness(
            dataDate,
            marketStatus?.expectedDataDate,
          )
          return (
            <div
              className="text-[10px] text-text-muted text-right"
              title={freshness.tooltip}
            >
              Data as of {formatDate(dataDate, false)} {freshness.indicator}
            </div>
          )
        })()}
    </div>
  )
}
