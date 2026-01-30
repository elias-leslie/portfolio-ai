import { PlusCircle, Trash2 } from 'lucide-react'
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { Account, PositionWithValue } from '@/lib/api/portfolio'
import {
  formatCurrency,
  formatPercent,
  getAccountPositions,
  getAccountTotalGain,
  getAccountTotalValue,
} from './portfolio-utils'
import { PositionTableRow } from './PositionTableRow'

interface AccountAccordionItemProps {
  account: Account
  positions: PositionWithValue[] | undefined
  onAddPosition?: (accountId: string) => void
  onDeleteAccount: (accountId: string, accountName: string) => void
  onEditPosition: (position: PositionWithValue) => void
  onDeletePosition: (positionId: string, symbol: string) => void
  isDeleting: boolean
  isDeletingPosition: boolean
}

export function AccountAccordionItem({
  account,
  positions: allPositions,
  onAddPosition,
  onDeleteAccount,
  onEditPosition,
  onDeletePosition,
  isDeleting,
  isDeletingPosition,
}: AccountAccordionItemProps) {
  const positions = getAccountPositions(account.id, allPositions)
  const totalValue = getAccountTotalValue(account.id, allPositions)
  const totalGain = getAccountTotalGain(account.id, allPositions)

  return (
    <AccordionItem
      value={account.id}
      className="border rounded-lg mb-3 last:mb-0"
    >
      <div className="flex items-center px-4">
        <AccordionTrigger className="flex-1 hover:no-underline py-4">
          <div className="flex items-center justify-between w-full pr-4">
            <div className="flex flex-col items-start gap-1">
              <div className="flex items-center gap-3">
                <span className="font-semibold text-base">
                  {account.name}
                </span>
                <span className="text-xs text-text-muted bg-surface-muted px-2 py-0.5 rounded">
                  {account.accountType}
                </span>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <span className="text-text-muted">
                  {positions.length} position
                  {positions.length !== 1 ? 's' : ''}
                </span>
                {positions.length > 0 && (
                  <>
                    <span className="text-text">
                      {formatCurrency(totalValue)}
                    </span>
                    <span
                      className={
                        totalGain >= 0 ? 'text-profit' : 'text-loss'
                      }
                    >
                      {formatPercent(totalGain)}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
        </AccordionTrigger>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            onDeleteAccount(account.id, account.name)
          }}
          disabled={isDeleting}
          className="h-8 w-8 p-0 ml-2"
        >
          <Trash2 className="h-4 w-4 text-loss" />
        </Button>
      </div>
      <AccordionContent className="px-4 pb-4">
        {onAddPosition && (
          <div className="mb-3 flex justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onAddPosition(account.id)}
            >
              <PlusCircle className="mr-2 h-4 w-4" />
              Add Position
            </Button>
          </div>
        )}
        {positions.length === 0 ? (
          <div className="py-8 text-center text-sm text-text-muted">
            No positions in this account yet. Click &quot;Add Position&quot;
            above to get started.
          </div>
        ) : (
          <div className="rounded-md border border-border bg-surface/50 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead className="text-right">Shares</TableHead>
                  <TableHead className="text-right">Cost Basis</TableHead>
                  <TableHead className="text-right">Current Price</TableHead>
                  <TableHead className="text-right">Value</TableHead>
                  <TableHead className="text-right">P&L $</TableHead>
                  <TableHead className="text-right">P&L %</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {positions.map((position) => (
                  <PositionTableRow
                    key={position.id}
                    position={position}
                    onEdit={onEditPosition}
                    onDelete={onDeletePosition}
                    isDeleting={isDeletingPosition}
                  />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </AccordionContent>
    </AccordionItem>
  )
}
