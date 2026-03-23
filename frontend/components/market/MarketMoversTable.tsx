'use client'

import { BarChart3, Loader2, TrendingDown, TrendingUp, Zap } from 'lucide-react'
import { useState } from 'react'
import type { MarketMoverItem } from '@/lib/api/market'
import { useMarketMovers } from '@/lib/hooks/useMarketIntelligence'
import { cn, formatRelativeTime } from '@/lib/utils'
import { MarketPanelMessage } from './MarketPanelMessage'

type Tab = 'gainers' | 'losers' | 'volume' | 'rvol'

function formatVolume(volume: number | null): string {
  if (!volume) return '-'
  if (volume >= 1_000_000) return `${(volume / 1_000_000).toFixed(1)}M`
  if (volume >= 1_000) return `${(volume / 1_000).toFixed(0)}K`
  return volume.toString()
}

function formatRvol(rvol: number | null): string {
  if (rvol === null || rvol === undefined) return '-'
  return `${rvol.toFixed(1)}x`
}

export function MarketMoversTable() {
  const [activeTab, setActiveTab] = useState<Tab>('gainers')
  const { data, isLoading, error } = useMarketMovers(10)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="h-5 w-5 animate-spin text-text-muted" />
      </div>
    )
  }

  if (error || !data) {
    return <MarketPanelMessage message="Unable to load market movers right now." />
  }

  const getItems = (): MarketMoverItem[] => {
    switch (activeTab) {
      case 'gainers':
        return data.gainers
      case 'losers':
        return data.losers
      case 'volume':
        return data.mostActive
      case 'rvol':
        return data.topRvol
    }
  }

  const items = getItems()

  const showRvolColumn = activeTab === 'rvol'

  if (items.length === 0) {
    return (
      <MarketPanelMessage message="No market mover data is available for this view yet." />
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Market Movers</h3>
        <div className="flex gap-0.5 rounded-lg border border-border/30 bg-surface-muted/50 p-0.5" role="group" aria-label="Market mover categories">
          {([
            { key: 'gainers' as Tab, icon: TrendingUp, label: 'Gainers', activeColor: 'text-gain' },
            { key: 'losers' as Tab, icon: TrendingDown, label: 'Losers', activeColor: 'text-loss' },
            { key: 'volume' as Tab, icon: BarChart3, label: 'Volume', activeColor: 'text-text' },
            { key: 'rvol' as Tab, icon: Zap, label: 'RVOL', activeColor: 'text-text' },
          ]).map(({ key, icon: TabIcon, label, activeColor }) => (
            <button
              key={key}
              type="button"
              aria-pressed={activeTab === key}
              onClick={() => setActiveTab(key)}
              className={cn(
                'flex cursor-pointer items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
                activeTab === key
                  ? `bg-surface ${activeColor} shadow-sm`
                  : 'text-text-muted hover:text-text',
              )}
            >
              <TabIcon className="h-3 w-3" />
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-muted border-b border-border/50">
              <th className="text-left py-1 font-medium">Symbol</th>
              <th className="text-left py-1 font-medium hidden md:table-cell whitespace-nowrap">
                Sector
              </th>
              <th className="text-right py-1 font-medium whitespace-nowrap">
                Price
              </th>
              <th className="text-right py-1 font-medium whitespace-nowrap">
                Change
              </th>
              {showRvolColumn ? (
                <th className="text-right py-1 font-medium whitespace-nowrap">
                  RVOL
                </th>
              ) : (
                <th className="text-right py-1 font-medium whitespace-nowrap hidden sm:table-cell">
                  Volume
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 10).map((item) => (
              <tr
                key={item.symbol}
                className="border-b border-border/30 hover:bg-surface-muted/50 transition-colors duration-150"
              >
                <td className="py-1">
                  <div className="flex flex-col">
                    <span className="font-semibold text-text">
                      {item.symbol}
                    </span>
                    {item.name && (
                      <span
                        className="text-text-muted truncate max-w-[140px]"
                        title={item.name}
                      >
                        {item.name}
                      </span>
                    )}
                  </div>
                </td>
                <td
                  className="py-1 text-text-muted hidden md:table-cell whitespace-nowrap"
                  title={item.sector || undefined}
                >
                  {item.sector || '-'}
                </td>
                <td className="text-right py-1 text-text whitespace-nowrap">
                  ${item.price.toFixed(2)}
                </td>
                <td
                  className={cn(
                    'text-right py-1 font-semibold whitespace-nowrap',
                    item.changePct >= 0 ? 'text-gain' : 'text-loss',
                  )}
                >
                  {item.changePct >= 0 ? '+' : ''}
                  {item.changePct.toFixed(2)}%
                </td>
                {showRvolColumn ? (
                  <td className="text-right py-1 text-text font-semibold whitespace-nowrap">
                    {formatRvol(item.rvol)}
                  </td>
                ) : (
                  <td className="text-right py-1 text-text-muted whitespace-nowrap hidden sm:table-cell">
                    {formatVolume(item.volume)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-1 text-xs text-text-muted text-right">
        {data.lastUpdated && `Updated ${formatRelativeTime(data.lastUpdated)}`}
      </div>
    </div>
  )
}
