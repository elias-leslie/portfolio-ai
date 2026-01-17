'use client'

import { formatDistanceToNow } from 'date-fns'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { StrategyListItem } from '@/lib/api/strategies'

interface StrategiesTableProps {
  strategies: StrategyListItem[]
  isLoading: boolean
  onSelectStrategy: (strategyId: string) => void
}

const strategyTypeColors: Record<string, string> = {
  momentum: 'bg-accent/10 text-accent',
  value: 'bg-gain/10 text-gain',
  event: 'bg-accent/10 text-accent',
  reversal: 'bg-warning/10 text-warning',
  defensive: 'bg-surface-muted text-text-muted',
}

const statusColors: Record<string, string> = {
  testing: 'bg-warning/10 text-warning',
  active: 'bg-gain/10 text-gain',
  archived: 'bg-surface-muted text-text-muted',
}

export function StrategiesTable({
  strategies,
  isLoading,
  onSelectStrategy,
}: StrategiesTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  if (strategies.length === 0) {
    return (
      <div className="py-8 text-center text-text-muted">
        <p>No strategies found.</p>
        <p className="text-sm">
          Click &quot;Generate Strategies&quot; to create new strategies.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Symbol</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Expected Sharpe</TableHead>
            <TableHead className="text-right">Live Sharpe</TableHead>
            <TableHead className="text-right">Win Rate</TableHead>
            <TableHead className="text-right">Trades</TableHead>
            <TableHead>Created</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {strategies.map((strategy) => (
            <TableRow
              key={strategy.id}
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => onSelectStrategy(strategy.id)}
            >
              <TableCell className="font-medium">{strategy.symbol}</TableCell>
              <TableCell
                className="max-w-[200px] truncate"
                title={strategy.name}
              >
                {strategy.name}
              </TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  className={strategyTypeColors[strategy.strategyType] || ''}
                >
                  {strategy.strategyType}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  className={statusColors[strategy.status] || ''}
                >
                  {strategy.status}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                {strategy.expectedSharpe?.toFixed(2) || '-'}
              </TableCell>
              <TableCell className="text-right">
                {strategy.liveSharpeRatio?.toFixed(2) || '-'}
              </TableCell>
              <TableCell className="text-right">
                {strategy.liveWinRate != null
                  ? `${(strategy.liveWinRate * 100).toFixed(0)}%`
                  : '-'}
              </TableCell>
              <TableCell className="text-right">
                {strategy.tradesCount || 0}
              </TableCell>
              <TableCell className="text-text-muted">
                {formatDistanceToNow(new Date(strategy.createdAt), {
                  addSuffix: true,
                })}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
