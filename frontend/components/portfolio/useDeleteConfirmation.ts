import { useState } from 'react'
import { toast } from 'sonner'
import type { PositionWithValue } from '@/lib/api/portfolio'
import { useDeleteAccount, useDeletePosition } from '@/lib/hooks/usePortfolio'
import { getAccountPositions } from './portfolio-utils'

type PendingAction =
  | { type: 'account'; id: string; name: string; positionCount: number }
  | { type: 'position'; id: string; symbol: string }
  | null

export function useDeleteConfirmation(positions: PositionWithValue[] | undefined) {
  const deleteAccount = useDeleteAccount()
  const deletePosition = useDeletePosition()
  const [pendingAction, setPendingAction] = useState<PendingAction>(null)

  const handleDeleteAccount = (accountId: string, accountName: string) => {
    const positionsInAccount = getAccountPositions(accountId, positions)
    setPendingAction({
      type: 'account',
      id: accountId,
      name: accountName,
      positionCount: positionsInAccount.length,
    })
  }

  const handleDeletePosition = (positionId: string, symbol: string) => {
    setPendingAction({ type: 'position', id: positionId, symbol })
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
          error instanceof Error ? error.message : 'Unable to complete the request'
        toast.error(`Failed to delete account "${pendingAction.name}": ${message}`)
      }
      throw error
    }
  }

  const dialogProps = {
    open: !!pendingAction,
    onOpenChange: (open: boolean) => {
      if (!open) setPendingAction(null)
    },
    title: pendingAction
      ? pendingAction.type === 'account'
        ? `Delete ${pendingAction.name}`
        : `Delete ${pendingAction.symbol} position`
      : 'Delete item',
    description: pendingAction
      ? pendingAction.type === 'account'
        ? pendingAction.positionCount > 0
          ? `This will remove ${pendingAction.positionCount} linked position${
              pendingAction.positionCount === 1 ? '' : 's'
            } permanently.`
          : 'This account has no positions and will be removed.'
        : 'This position will be removed from the account permanently.'
      : undefined,
    confirmLabel: pendingAction
      ? pendingAction.type === 'account'
        ? 'Delete account'
        : 'Delete position'
      : 'Delete',
    isPending: deleteAccount.isPending || deletePosition.isPending,
    onConfirm: confirmDeletion,
  }

  return {
    handleDeleteAccount,
    handleDeletePosition,
    dialogProps,
    isAccountDeletePending: deleteAccount.isPending,
    isPositionDeletePending: deletePosition.isPending,
  }
}
