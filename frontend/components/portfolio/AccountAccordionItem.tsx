import { PlusCircle, Trash2 } from 'lucide-react'
import { InfoBadge } from '@/components/shared/InfoBadge'
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
import type { HouseholdAccountSummary } from '@/lib/api/household'
import type { Account, PositionWithValue } from '@/lib/api/portfolio'
import { formatCurrency, formatPercent } from '@/lib/formatters'
import { formatRelativeTime } from '@/lib/utils'
import { PositionTableRow } from './PositionTableRow'
import { getAccountPositions } from './portfolio-utils'

interface AccountAccordionItemProps {
  account: Account
  linkedHouseholdAccount?: HouseholdAccountSummary | null
  positions: PositionWithValue[] | undefined
  onAddPosition?: (accountId?: string) => void
  onDeleteAccount: (accountId: string, accountName: string) => void
  onEditPosition: (position: PositionWithValue) => void
  onDeletePosition: (positionId: string, symbol: string) => void
  isDeleting: boolean
  isDeletingPosition: boolean
}

function linkedFreshnessVariant(status: string | null | undefined) {
  switch (status) {
    case 'fresh':
      return 'success' as const
    case 'aging':
      return 'warning' as const
    case 'stale':
      return 'secondary' as const
    default:
      return 'outline' as const
  }
}

export function AccountAccordionItem({
  account,
  linkedHouseholdAccount = null,
  positions: allPositions,
  onAddPosition,
  onDeleteAccount,
  onEditPosition,
  onDeletePosition,
  isDeleting,
  isDeletingPosition,
}: AccountAccordionItemProps) {
  const positions = getAccountPositions(account.id, allPositions)
  const cashBalance = linkedHouseholdAccount?.cashBalance ?? account.cashBalance
  const positionsValue = positions.reduce(
    (sum, position) => sum + (position.currentValue || 0),
    0,
  )
  const positionsCostBasis = positions.reduce(
    (sum, position) => sum + position.shares * position.costBasis,
    0,
  )
  const totalValue =
    positions.length > 0
      ? positionsValue + cashBalance
      : (linkedHouseholdAccount?.currentValue ?? cashBalance)
  const totalCostBasis =
    positions.length > 0 ? positionsCostBasis + cashBalance : cashBalance
  const totalGain =
    totalCostBasis > 0
      ? ((totalValue - totalCostBasis) / totalCostBasis) * 100
      : 0
  const hasCashBalance = cashBalance > 0
  const displayName = linkedHouseholdAccount?.label ?? account.name
  const linkedDetail = linkedHouseholdAccount
    ? [
        `Balance ${linkedHouseholdAccount.balanceFreshnessLabel.toLowerCase()}`,
        linkedHouseholdAccount.moneyRole === 'spend_driver'
          ? `Transactions ${linkedHouseholdAccount.transactionFreshnessLabel.toLowerCase()}`
          : null,
        linkedHouseholdAccount.lastEvidenceAt
          ? `Last evidence ${formatRelativeTime(linkedHouseholdAccount.lastEvidenceAt)}`
          : null,
      ]
        .filter(Boolean)
        .join(' · ')
    : null
  const quoteUpdatedAt =
    linkedHouseholdAccount?.quoteUpdatedAt ??
    positions
      .map((position) => position.priceUpdatedAt)
      .filter((value): value is string => Boolean(value))
      .sort()[0] ??
    null
  const quoteLabel =
    linkedHouseholdAccount?.quoteFreshnessLabel ??
    (positions.length > 0
      ? quoteUpdatedAt
        ? 'Live quotes'
        : 'Quotes pending'
      : null)
  const quoteDetail =
    positions.length > 0
      ? [
          `${positions.length} priced position${positions.length === 1 ? '' : 's'}`,
          quoteUpdatedAt
            ? `oldest quote ${formatRelativeTime(quoteUpdatedAt)}`
            : null,
          linkedHouseholdAccount?.quoteSource
            ? `source ${linkedHouseholdAccount.quoteSource}`
            : null,
        ]
          .filter(Boolean)
          .join(' · ')
      : null
  const evidenceLabel =
    linkedHouseholdAccount?.lastEvidenceAt != null ? 'Evidence' : null
  const evidenceDetail =
    linkedHouseholdAccount?.lastEvidenceAt != null
      ? [
          `Last evidence ${formatRelativeTime(linkedHouseholdAccount.lastEvidenceAt)}`,
          linkedHouseholdAccount.balanceFreshnessLabel,
        ].join(' · ')
      : null

  return (
    <AccordionItem
      value={account.id}
      className="rounded-xl border border-border/40 mb-3 last:mb-0"
    >
      <div className="flex items-center px-4">
        <AccordionTrigger className="flex-1 hover:no-underline py-4">
          <div className="flex items-center justify-between w-full pr-4">
            <div className="flex flex-col items-start gap-1">
              <div className="flex items-center gap-3">
                <span className="font-display italic text-lg tracking-tight">
                  {displayName}
                </span>
                <span className="text-xs text-text-muted bg-surface-muted px-2 py-0.5 rounded">
                  {account.accountType}
                </span>
                {linkedHouseholdAccount ? (
                  <InfoBadge
                    label={linkedHouseholdAccount.freshnessLabel}
                    detail={linkedDetail ?? undefined}
                    variant={linkedFreshnessVariant(
                      linkedHouseholdAccount.freshnessStatus,
                    )}
                  />
                ) : null}
              </div>
              <div className="flex items-center gap-4 text-sm">
                <span className="text-text-muted">
                  {positions.length} position
                  {positions.length !== 1 ? 's' : ''}
                </span>
                {(positions.length > 0 || hasCashBalance) && (
                  <>
                    <span className="text-text">
                      {formatCurrency(totalValue)}
                    </span>
                    {positions.length > 0 && (
                      <span
                        className={totalGain >= 0 ? 'text-gain' : 'text-loss'}
                      >
                        {formatPercent(totalGain, { decimals: 2, sign: true })}
                      </span>
                    )}
                    {hasCashBalance && (
                      <span className="text-text-muted">
                        Cash {formatCurrency(cashBalance)}
                      </span>
                    )}
                  </>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                <span className="rounded border border-border/40 bg-surface-muted/40 px-2 py-0.5 font-medium text-text-muted">
                  {linkedHouseholdAccount
                    ? 'Linked household account'
                    : 'Standalone position account'}
                </span>
                {quoteLabel ? (
                  <InfoBadge
                    label={quoteLabel}
                    detail={quoteDetail ?? undefined}
                    variant={linkedFreshnessVariant(
                      linkedHouseholdAccount?.quoteFreshnessStatus ??
                        (positions.length > 0 ? 'fresh' : undefined),
                    )}
                  />
                ) : null}
                {evidenceLabel ? (
                  <InfoBadge
                    label={evidenceLabel}
                    detail={evidenceDetail ?? undefined}
                    variant={linkedFreshnessVariant(
                      linkedHouseholdAccount?.balanceFreshnessStatus,
                    )}
                  />
                ) : (
                  <span>No linked household evidence</span>
                )}
                {linkedHouseholdAccount?.institutionName ? (
                  <span>{linkedHouseholdAccount.institutionName}</span>
                ) : null}
              </div>
            </div>
          </div>
        </AccordionTrigger>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            onDeleteAccount(account.id, displayName)
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
            {hasCashBalance
              ? `This account is currently cash only with ${formatCurrency(cashBalance)} available.`
              : 'No positions in this account yet. Click "Add Position" above to get started.'}
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border/40 bg-surface/50">
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
