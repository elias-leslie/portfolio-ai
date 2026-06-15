'use client'

import { PlusCircle } from 'lucide-react'
import { ConfirmActionDialog } from '@/components/shared/ConfirmActionDialog'
import { InfoBadge } from '@/components/shared/InfoBadge'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { Accordion } from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  formatCurrency,
  formatPercent,
  formatPnlDollars,
} from '@/lib/formatters'
import { useHouseholdDashboard } from '@/lib/hooks/useHousehold'
import { useAccounts, usePortfolio } from '@/lib/hooks/usePortfolio'
import { formatRelativeTime } from '@/lib/utils'
import { AccountAccordionItem } from './AccountAccordionItem'
import { AccountsWithPositionsSkeleton } from './AccountsWithPositionsSkeleton'
import { EditPositionDialog } from './EditPositionDialog'
import {
  getPositionCostBasisTotal,
  needsPositionBasisReview,
} from './portfolio-utils'
import { useDeleteConfirmation } from './useDeleteConfirmation'
import { useEditPositionForm } from './useEditPositionForm'

interface AccountsWithPositionsProps {
  onAddAccount?: () => void
  onAddPosition?: (accountId?: string) => void
}

function HoldingSummaryTile({
  label,
  value,
  detail,
  tone = 'neutral',
}: {
  label: string
  value: string
  detail: string
  tone?: 'neutral' | 'gain' | 'loss'
}) {
  return (
    <div className="rounded-xl border border-border/40 bg-surface-muted/20 px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">
        {label}
      </div>
      <div
        className={
          tone === 'gain'
            ? 'mt-1 text-xl font-semibold tabular-nums text-gain'
            : tone === 'loss'
              ? 'mt-1 text-xl font-semibold tabular-nums text-loss'
              : 'mt-1 text-xl font-semibold tabular-nums text-text'
        }
      >
        {value}
      </div>
      <div className="mt-1 text-xs text-text-muted">{detail}</div>
    </div>
  )
}

export interface AccountsWithPositionsContentProps
  extends AccountsWithPositionsProps {
  accounts: Awaited<ReturnType<typeof useAccounts>>['data']
  accountsLoading: boolean
  accountsFetching?: boolean
  accountsError?: Error | null
  evidenceInvestmentAccountsCount?: number | null
  onRetryAccounts?: () => void
}

export function AccountsWithPositionsContent({
  accounts,
  accountsLoading,
  accountsFetching,
  accountsError,
  evidenceInvestmentAccountsCount = null,
  onRetryAccounts,
  onAddAccount,
  onAddPosition,
}: AccountsWithPositionsContentProps) {
  const { data: household } = useHouseholdDashboard()
  const {
    data: portfolio,
    isLoading: portfolioLoading,
    error: portfolioError,
    refetch: refetchPortfolio,
    isFetching: portfolioFetching,
  } = usePortfolio()
  const del = useDeleteConfirmation(portfolio?.positions)
  const edit = useEditPositionForm()
  const confirmDialog = <ConfirmActionDialog {...del.dialogProps} />
  const positions = portfolio?.positions ?? []
  const positionValueTotal = positions.reduce(
    (sum, position) =>
      sum + (position.currentValue ?? position.sourceMarketValue ?? 0),
    0,
  )
  const costBasisTotal = positions.reduce(
    (sum, position) => sum + getPositionCostBasisTotal(position),
    0,
  )
  const cashBalanceTotal = portfolio?.cashBalanceTotal ?? 0
  const holdingsTotal = positionValueTotal + cashBalanceTotal
  const totalPnl = positionValueTotal - costBasisTotal
  const totalPnlPct =
    costBasisTotal > 0 ? (totalPnl / costBasisTotal) * 100 : null
  const snapTradePositionCount = positions.filter(
    (position) => position.source === 'snaptrade',
  ).length
  const basisReviewCount = positions.filter(needsPositionBasisReview).length
  const snapTradeSyncs = positions
    .map((position) => position.sourceUpdatedAt)
    .filter((value): value is string => Boolean(value))
    .sort()
  const latestSnapTradeSync =
    snapTradeSyncs.length > 0 ? snapTradeSyncs[snapTradeSyncs.length - 1] : null
  const showHoldingsSummary = positions.length > 0 || cashBalanceTotal > 0
  const linkedHouseholdAccountsByPortfolioAccountId = Object.fromEntries(
    (household?.accounts ?? [])
      .filter((account) => account.linkedPortfolioAccountId)
      .map((account) => [account.linkedPortfolioAccountId as string, account]),
  )
  const householdAccountsByHouseholdAccountId = Object.fromEntries(
    (household?.accounts ?? [])
      .filter((account) => account.householdAccountId)
      .map((account) => [account.householdAccountId as string, account]),
  )
  const householdInvestmentAccountsCount =
    evidenceInvestmentAccountsCount ??
    portfolio?.householdInvestmentAccountsCount ??
    null
  const accountCount = accounts?.length ?? 0
  const linkageCounts = (accounts ?? []).reduce(
    (counts, account) => {
      const state = account.householdLinkageState
      if (state === 'linked') counts.linked += 1
      if (state === 'stale_evidence') counts.stale += 1
      if (state === 'unmapped' || state === 'duplicate_candidate') {
        counts.unmapped += 1
      }
      return counts
    },
    { linked: 0, stale: 0, unmapped: 0 },
  )
  const householdCoverageDetail =
    householdInvestmentAccountsCount != null
      ? `Money Accounts tracks ${householdInvestmentAccountsCount} investment account${householdInvestmentAccountsCount === 1 ? '' : 's'}. Holdings totals include every live position account${linkageCounts.unmapped > 0 ? `, including ${linkageCounts.unmapped} unmapped account${linkageCounts.unmapped === 1 ? '' : 's'}` : ''}. ${linkageCounts.linked + linkageCounts.stale} of ${accountCount} position account${accountCount === 1 ? '' : 's'} currently link back to Money evidence.`
      : null
  const unmappedDetail =
    linkageCounts.unmapped > 0
      ? `These accounts remain included in holdings totals. Link or confirm evidence in Money Accounts to reconcile household coverage.`
      : null

  if (accountsLoading || portfolioLoading) {
    return (
      <>
        <AccountsWithPositionsSkeleton />
        {confirmDialog}
      </>
    )
  }

  if (accountsError || portfolioError) {
    return (
      <>
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Accounts & Positions</CardTitle>
                <CardDescription>
                  Account and position data is unavailable.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <LoadErrorState
              title="Failed to load portfolio accounts."
              detail={
                accountsError?.message ??
                portfolioError?.message ??
                'Unknown error'
              }
              onRetry={() => {
                onRetryAccounts?.()
                void refetchPortfolio?.()
              }}
              isRetrying={accountsFetching || portfolioFetching}
            />
          </CardContent>
        </Card>
        {confirmDialog}
      </>
    )
  }

  if (!accounts || accounts.length === 0) {
    return (
      <>
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Accounts & Positions</CardTitle>
                <CardDescription>
                  Organize your portfolio by account
                </CardDescription>
              </div>
              {onAddAccount && (
                <Button variant="outline" size="sm" onClick={onAddAccount}>
                  <PlusCircle className="mr-2 h-4 w-4" />
                  Add Account
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-xl border border-dashed border-border/50 bg-surface/40 p-6 text-center text-sm text-text-muted">
              No accounts yet. Create one above to start organizing your
              portfolio.
            </div>
          </CardContent>
        </Card>
        {confirmDialog}
      </>
    )
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Accounts & Positions</CardTitle>
              <CardDescription>
                {accounts.length} account{accounts.length !== 1 ? 's' : ''} •{' '}
                {portfolio?.positions.length || 0} position
                {portfolio?.positions.length !== 1 ? 's' : ''}
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {householdCoverageDetail ? (
                <InfoBadge
                  label={`${householdInvestmentAccountsCount} Money investment${householdInvestmentAccountsCount === 1 ? '' : 's'}`}
                  detail={householdCoverageDetail}
                  variant="outline"
                />
              ) : null}
              {snapTradePositionCount > 0 ? (
                <InfoBadge
                  label={`${snapTradePositionCount} SnapTrade lot${snapTradePositionCount === 1 ? '' : 's'}`}
                  detail={`Broker lots are wired into holdings rows${latestSnapTradeSync ? `; latest sync ${formatRelativeTime(latestSnapTradeSync)}` : ''}.`}
                  variant="success"
                />
              ) : null}
              {unmappedDetail ? (
                <InfoBadge
                  label={`${linkageCounts.unmapped} unmapped`}
                  detail={unmappedDetail}
                  variant="warning"
                />
              ) : null}
              {onAddPosition && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    onAddPosition(
                      accounts.length === 1 ? accounts[0].id : undefined,
                    )
                  }
                >
                  <PlusCircle className="mr-2 h-4 w-4" />
                  Add Position
                </Button>
              )}
              {onAddAccount && (
                <Button variant="outline" size="sm" onClick={onAddAccount}>
                  <PlusCircle className="mr-2 h-4 w-4" />
                  Add Account
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {showHoldingsSummary ? (
            <div className="mb-4 grid gap-3 md:grid-cols-4">
              <HoldingSummaryTile
                label="Total holdings"
                value={formatCurrency(holdingsTotal)}
                detail={`${positions.length} lot${positions.length === 1 ? '' : 's'} plus ${formatCurrency(cashBalanceTotal)} cash`}
              />
              <HoldingSummaryTile
                label="Invested"
                value={formatCurrency(positionValueTotal)}
                detail={`${snapTradePositionCount} SnapTrade-fed lot${snapTradePositionCount === 1 ? '' : 's'}`}
              />
              <HoldingSummaryTile
                label="Open P&L"
                value={`${formatPnlDollars(totalPnl)} (${formatPercent(totalPnlPct, { decimals: 2, sign: true })})`}
                detail="Using per-lot cost basis"
                tone={totalPnl >= 0 ? 'gain' : 'loss'}
              />
              <HoldingSummaryTile
                label="Basis checks"
                value={String(basisReviewCount)}
                detail={
                  basisReviewCount > 0
                    ? 'Review extreme basis/quote gaps'
                    : 'No extreme basis gaps'
                }
                tone={basisReviewCount > 0 ? 'loss' : 'neutral'}
              />
            </div>
          ) : null}
          {positions.length === 0 ? (
            <div className="mb-4 rounded-xl border border-border/50 bg-surface-muted/20 p-4 text-sm text-text-muted">
              Accounts exist, but no live positions are tracked yet.
            </div>
          ) : null}
          <Accordion type="single" collapsible className="w-full">
            {accounts.map((account) => (
              <AccountAccordionItem
                key={account.id}
                account={account}
                linkedHouseholdAccount={
                  linkedHouseholdAccountsByPortfolioAccountId[account.id] ??
                  (account.householdAccountId
                    ? householdAccountsByHouseholdAccountId[
                        account.householdAccountId
                      ]
                    : null) ??
                  null
                }
                positions={portfolio?.positions}
                onAddPosition={onAddPosition}
                onDeleteAccount={del.handleDeleteAccount}
                onEditPosition={edit.handleEditPosition}
                onDeletePosition={del.handleDeletePosition}
                isDeleting={del.isAccountDeletePending}
                isDeletingPosition={del.isPositionDeletePending}
              />
            ))}
          </Accordion>
        </CardContent>
      </Card>
      <EditPositionDialog
        open={edit.editOpen}
        onOpenChange={(open) => {
          if (!open) edit.resetEditForm()
        }}
        accounts={accounts}
        accountId={edit.editAccountId}
        symbol={edit.editSymbol}
        shares={edit.editShares}
        costBasis={edit.editCostBasis}
        positionType={edit.editPositionType}
        errors={edit.editFormErrors}
        canSubmit={edit.canUpdatePosition}
        isPending={edit.isPending}
        onAccountChange={edit.setEditAccountId}
        onSymbolChange={edit.setEditSymbol}
        onSharesChange={edit.setEditShares}
        onCostBasisChange={edit.setEditCostBasis}
        onPositionTypeChange={edit.setEditPositionType}
        onUpdate={edit.handleUpdatePosition}
      />
      {confirmDialog}
    </>
  )
}

export function AccountsWithPositions(props: AccountsWithPositionsProps) {
  const {
    data: accounts,
    isLoading: accountsLoading,
    isFetching: accountsFetching,
    error: accountsError,
    refetch,
  } = useAccounts()

  return (
    <AccountsWithPositionsContent
      {...props}
      accounts={accounts}
      accountsLoading={accountsLoading}
      accountsFetching={accountsFetching}
      accountsError={accountsError}
      onRetryAccounts={() => {
        void refetch()
      }}
    />
  )
}
