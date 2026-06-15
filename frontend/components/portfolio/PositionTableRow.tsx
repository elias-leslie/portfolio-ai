import { Pencil, Trash2 } from 'lucide-react'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { TableCell, TableRow } from '@/components/ui/table'
import type { PositionWithValue } from '@/lib/api/portfolio'
import {
  formatCurrency,
  formatPercent,
  formatPnlDollars,
} from '@/lib/formatters'
import { cn } from '@/lib/utils'
import {
  getPositionCostBasisTotal,
  getPositionPnlDollars,
  getPositionPnlPercent,
  needsPositionBasisReview,
} from './portfolio-utils'

interface PositionTableRowProps {
  position: PositionWithValue
  onEdit: (position: PositionWithValue) => void
  onDelete: (positionId: string, symbol: string) => void
  isDeleting: boolean
}

function formatSecurityKind(value: string | null | undefined) {
  if (!value) return null
  return value.replace(/_/g, ' ').toUpperCase()
}

export function PositionTableRow({
  position,
  onEdit,
  onDelete,
  isDeleting,
}: PositionTableRowProps) {
  const costBasisTotal = getPositionCostBasisTotal(position)
  const pnlDollars = getPositionPnlDollars(position)
  const pnlPercent = getPositionPnlPercent(position)
  const basisNeedsReview = needsPositionBasisReview(position)
  const isSnapTradeLot = position.source === 'snaptrade'
  const lotSource = isSnapTradeLot ? 'SnapTrade lot' : 'Manual lot'
  const timeVerb = isSnapTradeLot ? 'synced' : 'updated'
  const updatedAt =
    position.sourceUpdatedAt ?? position.priceUpdatedAt ?? position.updatedAt
  const securityKind = formatSecurityKind(position.securityKind)
  const rawSymbol =
    position.rawSymbol &&
    position.rawSymbol.toUpperCase() !== position.symbol.toUpperCase()
      ? position.rawSymbol
      : null
  const brokerPriceDiffers =
    position.sourcePrice != null &&
    position.currentPrice != null &&
    Math.abs(position.sourcePrice - position.currentPrice) >= 0.01
  const brokerValueDiffers =
    position.sourceMarketValue != null &&
    position.currentValue != null &&
    Math.abs(position.sourceMarketValue - position.currentValue) >= 1
  const currentPriceLabel =
    position.currentPrice != null ? formatCurrency(position.currentPrice) : '—'
  const currentValueLabel =
    position.currentValue != null ? formatCurrency(position.currentValue) : '—'

  return (
    <TableRow>
      <TableCell>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{position.symbol}</span>
          {securityKind ? (
            <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
              {securityKind}
            </Badge>
          ) : null}
        </div>
        <div className="text-xs text-text-muted">
          {lotSource} · {timeVerb} <RelativeTime value={updatedAt} />
        </div>
        {rawSymbol ? (
          <div className="text-xs text-text-muted">raw {rawSymbol}</div>
        ) : null}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {position.shares.toLocaleString('en-US', {
          maximumFractionDigits: 4,
        })}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {formatCurrency(position.costBasis)}
        <div className="text-xs font-normal text-text-muted">
          total {formatCurrency(costBasisTotal)}
        </div>
        {position.averagePurchasePrice != null ? (
          <div className="text-xs font-normal text-text-muted">
            avg paid {formatCurrency(position.averagePurchasePrice)}
          </div>
        ) : null}
        {basisNeedsReview ? (
          <Badge
            variant="warning"
            className="mt-1"
            title="Review this lot because basis per share is far below the current price."
          >
            Basis review
          </Badge>
        ) : null}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {currentPriceLabel}
        {position.priceSource ? (
          <div className="text-xs font-normal text-text-muted">
            {position.priceSource === 'snaptrade'
              ? 'broker snapshot'
              : `${position.priceSource} quote`}
          </div>
        ) : null}
        {brokerPriceDiffers ? (
          <div className="text-xs font-normal text-text-muted">
            broker {formatCurrency(position.sourcePrice)}
          </div>
        ) : null}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {currentValueLabel}
        {brokerValueDiffers ? (
          <div className="text-xs font-normal text-text-muted">
            broker {formatCurrency(position.sourceMarketValue)}
          </div>
        ) : null}
      </TableCell>
      <TableCell
        className={cn(
          'text-right tabular-nums font-semibold',
          pnlDollars >= 0 ? 'text-gain' : 'text-loss',
        )}
      >
        {position.currentValue != null ? formatPnlDollars(pnlDollars) : '—'}
      </TableCell>
      <TableCell
        className={cn(
          'text-right tabular-nums',
          pnlPercent >= 0 ? 'text-gain' : 'text-loss',
        )}
      >
        {position.currentValue != null
          ? formatPercent(pnlPercent, { decimals: 2, sign: true })
          : '—'}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onEdit(position)}
            className="h-8 w-8 p-0"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(position.id, position.symbol)}
            disabled={isDeleting}
            className="h-8 w-8 p-0"
          >
            <Trash2 className="h-3.5 w-3.5 text-loss" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}
