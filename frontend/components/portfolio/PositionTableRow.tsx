import { Pencil, Trash2 } from 'lucide-react'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { Button } from '@/components/ui/button'
import { TableCell, TableRow } from '@/components/ui/table'
import type { PositionWithValue } from '@/lib/api/portfolio'
import {
  formatCurrency,
  formatPercent,
  formatPnlDollars,
} from '@/lib/formatters'
import { cn } from '@/lib/utils'

interface PositionTableRowProps {
  position: PositionWithValue
  onEdit: (position: PositionWithValue) => void
  onDelete: (positionId: string, symbol: string) => void
  isDeleting: boolean
}

export function PositionTableRow({
  position,
  onEdit,
  onDelete,
  isDeleting,
}: PositionTableRowProps) {
  const costBasisTotal = position.shares * position.costBasis
  const pnlDollars = position.currentValue
    ? position.currentValue - costBasisTotal
    : 0
  const pnlPercent =
    costBasisTotal > 0 ? (pnlDollars / costBasisTotal) * 100 : 0

  return (
    <TableRow>
      <TableCell>
        <div className="font-medium">{position.symbol}</div>
        <div className="text-xs text-text-muted">
          Manual lot · updated <RelativeTime value={position.updatedAt} />
        </div>
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {position.shares}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {formatCurrency(position.costBasis)}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {position.currentPrice ? formatCurrency(position.currentPrice) : '—'}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {position.currentValue ? formatCurrency(position.currentValue) : '—'}
      </TableCell>
      <TableCell
        className={cn(
          'text-right tabular-nums font-semibold',
          pnlDollars >= 0 ? 'text-gain' : 'text-loss',
        )}
      >
        {position.currentValue ? formatPnlDollars(pnlDollars) : '—'}
      </TableCell>
      <TableCell
        className={cn(
          'text-right tabular-nums',
          pnlPercent >= 0 ? 'text-gain' : 'text-loss',
        )}
      >
        {position.currentValue
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
