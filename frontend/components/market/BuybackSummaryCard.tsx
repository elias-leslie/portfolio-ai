'use client'

import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { apiRequest } from '@/lib/api/client'

interface BuybackSummary {
  symbol: string
  buybackCount: number
  totalBuybacks: number
  latestBuyback: string | null
}

interface BuybackSummaryResponse {
  summaries: BuybackSummary[]
  totalSymbols: number
}

function formatBuybackAmount(amount: number): string {
  if (amount >= 1e9) {
    return `$${(amount / 1e9).toFixed(1)}B`
  }
  if (amount >= 1e6) {
    return `$${(amount / 1e6).toFixed(0)}M`
  }
  return `$${amount.toLocaleString()}`
}

export function BuybackSummaryCard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['market', 'buyback-summary'],
    queryFn: () =>
      apiRequest<BuybackSummaryResponse>(
        '/api/market/corporate-actions/summary',
      ),
    staleTime: 1000 * 60 * 30, // 30 minutes
  })

  if (isLoading) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-center h-24">
          <Loader2 className="h-5 w-5 animate-spin text-text-muted" />
        </div>
      </Card>
    )
  }

  if (error || !data?.summaries?.length) {
    return null // Don't show card if no data
  }

  // Show top 5 by total buybacks
  const topBuybacks = data.summaries.slice(0, 5)

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold text-text mb-3">
        Share Buybacks (Quarterly)
      </h3>

      <div className="space-y-2">
        {topBuybacks.map((summary) => (
          <div
            key={summary.symbol}
            className="flex items-center justify-between text-sm"
          >
            <span className="font-medium text-text">{summary.symbol}</span>
            <div className="flex items-center gap-3">
              <span className="text-text-muted">
                {summary.buybackCount} qtr
                {summary.buybackCount !== 1 ? 's' : ''}
              </span>
              <span className="font-medium text-gain">
                {formatBuybackAmount(summary.totalBuybacks)}
              </span>
            </div>
          </div>
        ))}
      </div>

      {data.totalSymbols > 5 && (
        <div className="mt-2 pt-2 border-t border-border/30 text-xs text-text-muted">
          +{data.totalSymbols - 5} more symbols with buybacks
        </div>
      )}
    </Card>
  )
}
