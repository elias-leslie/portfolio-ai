'use client'

import { PlusCircle } from 'lucide-react'
import { ConfirmActionDialog } from '@/components/shared/ConfirmActionDialog'
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
import { useAccounts, usePortfolio } from '@/lib/hooks/usePortfolio'
import { AccountAccordionItem } from './AccountAccordionItem'
import { AccountsWithPositionsSkeleton } from './AccountsWithPositionsSkeleton'
import { EditPositionDialog } from './EditPositionDialog'
import { useDeleteConfirmation } from './useDeleteConfirmation'
import { useEditPositionForm } from './useEditPositionForm'

interface AccountsWithPositionsProps {
  onAddAccount?: () => void
  onAddPosition?: (accountId?: string) => void
}

export interface AccountsWithPositionsContentProps extends AccountsWithPositionsProps {
  accounts: Awaited<ReturnType<typeof useAccounts>>['data']
  accountsLoading: boolean
  accountsFetching?: boolean
  accountsError?: Error | null
  onRetryAccounts?: () => void
}

export function AccountsWithPositionsContent({
  accounts,
  accountsLoading,
  accountsFetching,
  accountsError,
  onRetryAccounts,
  onAddAccount,
  onAddPosition,
}: AccountsWithPositionsContentProps) {
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
                  Reload account and position data before making portfolio edits.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <LoadErrorState
              title="Failed to load portfolio accounts."
              detail={accountsError?.message ?? portfolioError?.message ?? 'Unknown error'}
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
                <CardDescription>Organize your portfolio by account</CardDescription>
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
              No accounts yet. Create one above to start organizing your portfolio.
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
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Accounts & Positions</CardTitle>
              <CardDescription>
                {accounts.length} account{accounts.length !== 1 ? 's' : ''} •{' '}
                {portfolio?.positions.length || 0} position
                {portfolio?.positions.length !== 1 ? 's' : ''}
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {onAddPosition && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    onAddPosition(accounts.length === 1 ? accounts[0].id : undefined)
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
          {portfolio?.positions.length === 0 ? (
            <div className="mb-4 rounded-xl border border-border/50 bg-surface-muted/20 p-4 text-sm text-text-muted">
              You have accounts set up but no live positions yet. Add your first holding to
              start tracking concentration, sizing, and performance.
            </div>
          ) : null}
          <Accordion type="single" collapsible className="w-full">
            {accounts.map((account) => (
              <AccountAccordionItem
                key={account.id}
                account={account}
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
