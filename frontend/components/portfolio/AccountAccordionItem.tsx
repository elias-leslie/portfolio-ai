import { ArrowRight, PlusCircle, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { useMemo, useState } from 'react'
import { InfoBadge } from '@/components/shared/InfoBadge'
import {
  nextSortDirection,
  SortableTableHeader,
  type SortDirection,
} from '@/components/shared/SortableTableHeader'
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
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
import {
  getAccountPositions,
  getPositionCostBasisTotal,
  getPositionPnlDollars,
  getPositionPnlPercent,
  needsPositionBasisReview,
} from './portfolio-utils'

type PositionSortKey =
  | 'symbol'
  | 'shares'
  | 'costBasis'
  | 'currentPrice'
  | 'value'
  | 'pnlDollars'
  | 'pnlPercent'

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

function linkageVariant(state: string | null | undefined) {
  switch (state) {
    case 'linked':
      return 'success' as const
    case 'stale_evidence':
    case 'duplicate_candidate':
      return 'warning' as const
    case 'unmapped':
      return 'secondary' as const
    default:
      return 'outline' as const
  }
}

function fallbackLinkageLabel(
  account: Account,
  linkedHouseholdAccount?: HouseholdAccountSummary | null,
) {
  if (account.accountType === 'paper') {
    return 'Standalone by design'
  }
  return linkedHouseholdAccount
    ? 'Linked household account'
    : 'Unmapped investment account'
}

function fallbackLinkageDetail(
  account: Account,
  linkedHouseholdAccount?: HouseholdAccountSummary | null,
) {
  if (account.accountType === 'paper') {
    return 'Paper account excluded from household evidence reconciliation.'
  }
  if (linkedHouseholdAccount) {
    return `Money Accounts links this to ${linkedHouseholdAccount.label}. Evidence is ${linkedHouseholdAccount.freshnessLabel.toLowerCase()}.`
  }
  return 'Included in holdings totals, but Money Accounts has no linked household evidence.'
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
  const [sortKey, setSortKey] = useState<PositionSortKey>('value')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const positions = getAccountPositions(account.id, allPositions)
  const sortedPositions = useMemo(() => {
    const direction = sortDirection === 'asc' ? 1 : -1
    return [...positions].sort((left, right) => {
      let result = 0
      switch (sortKey) {
        case 'symbol':
          result = left.symbol.localeCompare(right.symbol, undefined, {
            sensitivity: 'base',
          })
          break
        case 'shares':
          result = left.shares - right.shares
          break
        case 'costBasis':
          result = left.costBasis - right.costBasis
          break
        case 'currentPrice':
          result = (left.currentPrice || 0) - (right.currentPrice || 0)
          break
        case 'value':
          result = (left.currentValue || 0) - (right.currentValue || 0)
          break
        case 'pnlDollars':
          result = getPositionPnlDollars(left) - getPositionPnlDollars(right)
          break
        case 'pnlPercent':
          result = getPositionPnlPercent(left) - getPositionPnlPercent(right)
          break
      }
      return (
        result * direction ||
        left.symbol.localeCompare(right.symbol, undefined, {
          sensitivity: 'base',
        })
      )
    })
  }, [positions, sortDirection, sortKey])
  const cashBalance = linkedHouseholdAccount?.cashBalance ?? account.cashBalance
  const positionsValue = positions.reduce(
    (sum, position) => sum + (position.currentValue || 0),
    0,
  )
  const positionsCostBasis = positions.reduce(
    (sum, position) => sum + getPositionCostBasisTotal(position),
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
  const householdLinkageState =
    account.householdLinkageState ??
    (linkedHouseholdAccount ? 'linked' : undefined)
  const householdLinkageLabel =
    account.householdLinkageLabel ??
    fallbackLinkageLabel(account, linkedHouseholdAccount)
  const householdLinkageDetail =
    account.householdLinkageDetail ??
    fallbackLinkageDetail(account, linkedHouseholdAccount)
  const showLinkageAction =
    Boolean(account.householdLinkageActionHref) &&
    (householdLinkageState === 'unmapped' ||
      householdLinkageState === 'duplicate_candidate' ||
      householdLinkageState === 'stale_evidence')
  const linkageActionLabel =
    householdLinkageState === 'stale_evidence'
      ? 'Refresh evidence'
      : 'Review in Money'
  const basisReviewCount = positions.filter(needsPositionBasisReview).length
  const snapTradePositionCount = positions.filter(
    (position) => position.source === 'snaptrade',
  ).length
  const snapTradeSyncs = positions
    .map((position) => position.sourceUpdatedAt)
    .filter((value): value is string => Boolean(value))
    .sort()
  const snapTradeLastSyncedAt =
    snapTradeSyncs.length > 0 ? snapTradeSyncs[snapTradeSyncs.length - 1] : null
  const snapTradeDetail =
    snapTradePositionCount > 0
      ? [
          'Broker-supplied lots include snapshot price, market value, basis, and security type when available.',
          snapTradeLastSyncedAt
            ? `Last sync ${formatRelativeTime(snapTradeLastSyncedAt)}`
            : null,
        ]
          .filter(Boolean)
          .join(' ')
      : null

  function defaultSortDirection(field: PositionSortKey): SortDirection {
    return field === 'symbol' ? 'asc' : 'desc'
  }

  function handleSort(field: PositionSortKey) {
    setSortDirection((current) =>
      nextSortDirection(sortKey, field, current, defaultSortDirection(field)),
    )
    setSortKey(field)
  }

  return (
    <AccordionItem
      value={account.id}
      className="rounded-xl border border-border/40 mb-3 last:mb-0"
    >
      <div className="flex items-center px-4">
        <AccordionTrigger className="flex-1 hover:no-underline py-4">
          <div className="flex min-w-0 items-center justify-between w-full pr-4">
            <div className="flex flex-col items-start gap-1">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
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
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
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
                    {basisReviewCount > 0 ? (
                      <InfoBadge
                        label={`${basisReviewCount} basis review${basisReviewCount === 1 ? '' : 's'}`}
                        detail="Review lots where basis per share is far below the current quote. This can be valid for very old lots, but it is often a stale or partial broker basis."
                        variant="warning"
                      />
                    ) : null}
                  </>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                <Badge variant={linkageVariant(householdLinkageState)}>
                  {householdLinkageLabel}
                </Badge>
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
                ) : null}
                {snapTradePositionCount > 0 ? (
                  <InfoBadge
                    label={`${snapTradePositionCount} SnapTrade lot${snapTradePositionCount === 1 ? '' : 's'}`}
                    detail={snapTradeDetail ?? undefined}
                    variant="success"
                  />
                ) : null}
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
        {showLinkageAction ? (
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/40 bg-surface-muted/30 px-3 py-2 text-sm text-text-muted">
            <span>{householdLinkageDetail}</span>
            <Button asChild variant="outline" size="sm">
              <Link href={account.householdLinkageActionHref ?? '/money'}>
                {linkageActionLabel}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        ) : null}
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
                  <TableHead>
                    <SortableTableHeader
                      field="symbol"
                      label="Symbol"
                      activeField={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                    />
                  </TableHead>
                  <TableHead className="text-right">
                    <SortableTableHeader
                      field="shares"
                      label="Shares"
                      activeField={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="text-right">
                    <SortableTableHeader
                      field="costBasis"
                      label="Cost / sh"
                      activeField={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="text-right">
                    <SortableTableHeader
                      field="currentPrice"
                      label="Price"
                      activeField={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="text-right">
                    <SortableTableHeader
                      field="value"
                      label="Value"
                      activeField={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="text-right">
                    <SortableTableHeader
                      field="pnlDollars"
                      label="P&L $"
                      activeField={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="text-right">
                    <SortableTableHeader
                      field="pnlPercent"
                      label="P&L %"
                      activeField={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedPositions.map((position) => (
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
