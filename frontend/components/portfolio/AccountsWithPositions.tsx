'use client'

import { PlusCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
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
import type { PositionWithValue } from '@/lib/api/portfolio'
import {
  useAccounts,
  useDeleteAccount,
  useDeletePosition,
  usePortfolio,
  useUpdatePosition,
} from '@/lib/hooks/usePortfolio'
import { AccountAccordionItem } from './AccountAccordionItem'
import { AccountsWithPositionsSkeleton } from './AccountsWithPositionsSkeleton'
import { EditPositionDialog } from './EditPositionDialog'
import { getAccountPositions } from './portfolio-utils'
import {
  getPositionFormErrors,
  isPositionFormValid,
  normalizeSymbol,
  type PositionType,
} from './portfolio-form-utils'

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
  const deleteAccount = useDeleteAccount()
  const deletePosition = useDeletePosition()
  const updatePosition = useUpdatePosition()
  const [pendingAction, setPendingAction] = useState<
    | { type: 'account'; id: string; name: string; positionCount: number }
    | { type: 'position'; id: string; symbol: string }
    | null
  >(null)

  // Edit position dialog state
  const [editOpen, setEditOpen] = useState(false)
  const [editingPosition, setEditingPosition] =
    useState<PositionWithValue | null>(null)
  const [editAccountId, setEditAccountId] = useState('')
  const [editSymbol, setEditSymbol] = useState('')
  const [editShares, setEditShares] = useState('')
  const [editCostBasis, setEditCostBasis] = useState('')
  const [editPositionType, setEditPositionType] = useState<PositionType>('long')
  const editFormErrors = getPositionFormErrors({
    accountId: editAccountId,
    symbol: editSymbol,
    shares: editShares,
    costBasis: editCostBasis,
  })
  const canUpdatePosition = Boolean(editingPosition) && isPositionFormValid(editFormErrors)

  // Helper to get positions for account
  const getPositionsForAccount = (accountId: string) => {
    return getAccountPositions(accountId, portfolio?.positions)
  }

  const resetEditForm = () => {
    setEditOpen(false)
    setEditingPosition(null)
    setEditAccountId('')
    setEditSymbol('')
    setEditShares('')
    setEditCostBasis('')
    setEditPositionType('long')
  }

  const handleDeleteAccount = (accountId: string, accountName: string) => {
    const positionsInAccount = getPositionsForAccount(accountId)
    setPendingAction({
      type: 'account',
      id: accountId,
      name: accountName,
      positionCount: positionsInAccount.length,
    })
  }

  const handleDeletePosition = (positionId: string, symbol: string) => {
    setPendingAction({
      type: 'position',
      id: positionId,
      symbol,
    })
  }

  const handleEditPosition = (position: PositionWithValue) => {
    setEditingPosition(position)
    setEditAccountId(position.accountId)
    setEditSymbol(position.symbol)
    setEditShares(position.shares.toString())
    setEditCostBasis(position.costBasis.toString())
    setEditPositionType(position.positionType as PositionType)
    setEditOpen(true)
  }

  const handleUpdatePosition = () => {
    if (!editingPosition || !canUpdatePosition) return

    updatePosition.mutate(
      {
        positionId: editingPosition.id,
        data: {
          accountId: editAccountId,
          symbol: normalizeSymbol(editSymbol),
          shares: parseFloat(editShares),
          costBasis: parseFloat(editCostBasis),
          positionType: editPositionType,
        },
      },
      {
        onSuccess: () => {
          resetEditForm()
        },
      },
    )
  }

  const confirmDeletion = async () => {
    if (!pendingAction) return
    try {
      if (pendingAction.type === 'account') {
        await deleteAccount.mutateAsync(pendingAction.id)
        toast.success(`Deleted account "${pendingAction.name}".`)
      } else {
        await deletePosition.mutateAsync(pendingAction.id)
      }
    } catch (error) {
      if (pendingAction.type === 'account') {
        const message =
          error instanceof Error
            ? error.message
            : 'Unable to complete the request'
        toast.error(`Failed to delete account "${pendingAction.name}": ${message}`)
      }
      throw error
    }
  }

  const confirmDialog = (
    <ConfirmActionDialog
      open={!!pendingAction}
      onOpenChange={(open) => {
        if (!open) {
          setPendingAction(null)
        }
      }}
      title={
        pendingAction
          ? pendingAction.type === 'account'
            ? `Delete ${pendingAction.name}`
            : `Delete ${pendingAction.symbol} position`
          : 'Delete item'
      }
      description={
        pendingAction
          ? pendingAction.type === 'account'
            ? pendingAction.positionCount > 0
              ? `This will remove ${pendingAction.positionCount} linked position${
                  pendingAction.positionCount === 1 ? '' : 's'
                } permanently.`
              : 'This account has no positions and will be removed.'
            : 'This position will be removed from the account permanently.'
          : undefined
      }
      confirmLabel={
        pendingAction
          ? pendingAction.type === 'account'
            ? 'Delete account'
            : 'Delete position'
          : 'Delete'
      }
      isPending={deleteAccount.isPending || deletePosition.isPending}
      onConfirm={confirmDeletion}
    />
  )

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
                void refetchPortfolio()
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
            <div className="text-sm text-text-muted">
              No accounts yet. Click &quot;Add Account&quot; above to start
              managing your portfolio.
            </div>
          </CardContent>
        </Card>
        {confirmDialog}
      </>
    )
  }

  const handleHeaderAddPosition = () => {
    if (!onAddPosition) {
      return
    }

    onAddPosition(accounts.length === 1 ? accounts[0].id : undefined)
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
                <Button variant="outline" size="sm" onClick={handleHeaderAddPosition}>
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
              You have accounts set up but no live positions yet. Add your first holding to start tracking concentration, sizing, and performance.
            </div>
          ) : null}
          <Accordion type="single" collapsible className="w-full">
            {accounts.map((account) => (
              <AccountAccordionItem
                key={account.id}
                account={account}
                positions={portfolio?.positions}
                onAddPosition={onAddPosition}
                onDeleteAccount={handleDeleteAccount}
                onEditPosition={handleEditPosition}
                onDeletePosition={handleDeletePosition}
                isDeleting={deleteAccount.isPending}
                isDeletingPosition={deletePosition.isPending}
              />
            ))}
          </Accordion>
        </CardContent>
      </Card>

      <EditPositionDialog
        open={editOpen}
        onOpenChange={(open) => {
          if (!open) {
            resetEditForm()
          } else {
            setEditOpen(true)
          }
        }}
        accounts={accounts}
        accountId={editAccountId}
        symbol={editSymbol}
        shares={editShares}
        costBasis={editCostBasis}
        positionType={editPositionType}
        errors={editFormErrors}
        canSubmit={canUpdatePosition}
        isPending={updatePosition.isPending}
        onAccountChange={setEditAccountId}
        onSymbolChange={setEditSymbol}
        onSharesChange={setEditShares}
        onCostBasisChange={setEditCostBasis}
        onPositionTypeChange={setEditPositionType}
        onUpdate={handleUpdatePosition}
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
