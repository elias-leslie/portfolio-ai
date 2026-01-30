'use client'

import { PlusCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ConfirmActionDialog } from '@/components/shared/ConfirmActionDialog'
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

type PositionType = 'long' | 'short'

interface AccountsWithPositionsProps {
  onAddAccount?: () => void
  onAddPosition?: (accountId: string) => void
}

export function AccountsWithPositions({
  onAddAccount,
  onAddPosition,
}: AccountsWithPositionsProps) {
  const { data: accounts, isLoading: accountsLoading } = useAccounts()
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio()
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

  // Helper to get positions for account
  const getPositionsForAccount = (accountId: string) => {
    return getAccountPositions(accountId, portfolio?.positions)
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
    if (!editingPosition) return

    updatePosition.mutate(
      {
        positionId: editingPosition.id,
        data: {
          accountId: editAccountId,
          symbol: editSymbol.toUpperCase().trim(),
          shares: parseFloat(editShares),
          costBasis: parseFloat(editCostBasis),
          positionType: editPositionType,
        },
      },
      {
        onSuccess: () => {
          setEditOpen(false)
          setEditingPosition(null)
          toast.success('Position updated successfully!')
        },
        onError: (error) => {
          toast.error(`Failed to update position: ${error.message}`)
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
        toast.success(`${pendingAction.symbol} position deleted.`)
      }
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Unable to complete the request'
      const target =
        pendingAction.type === 'account'
          ? `account "${pendingAction.name}"`
          : `${pendingAction.symbol} position`
      toast.error(`Failed to delete ${target}: ${message}`)
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
            {onAddAccount && (
              <Button variant="outline" size="sm" onClick={onAddAccount}>
                <PlusCircle className="mr-2 h-4 w-4" />
                Add Account
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
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
        onOpenChange={setEditOpen}
        accounts={accounts}
        accountId={editAccountId}
        symbol={editSymbol}
        shares={editShares}
        costBasis={editCostBasis}
        positionType={editPositionType}
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
