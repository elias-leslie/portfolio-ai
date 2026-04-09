import { useState } from 'react'
import type { PositionWithValue } from '@/lib/api/portfolio'
import { useUpdatePosition } from '@/lib/hooks/usePortfolio'
import {
  getPositionFormErrors,
  isPositionFormValid,
  normalizeSymbol,
  type PositionType,
} from './portfolio-form-utils'

export function useEditPositionForm() {
  const updatePosition = useUpdatePosition()
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
  const canUpdatePosition =
    Boolean(editingPosition) && isPositionFormValid(editFormErrors)

  const resetEditForm = () => {
    setEditOpen(false)
    setEditingPosition(null)
    setEditAccountId('')
    setEditSymbol('')
    setEditShares('')
    setEditCostBasis('')
    setEditPositionType('long')
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
      { onSuccess: resetEditForm },
    )
  }

  return {
    editOpen,
    editAccountId,
    editSymbol,
    editShares,
    editCostBasis,
    editPositionType,
    editFormErrors,
    canUpdatePosition,
    isPending: updatePosition.isPending,
    handleEditPosition,
    handleUpdatePosition,
    resetEditForm,
    setEditAccountId,
    setEditSymbol,
    setEditShares,
    setEditCostBasis,
    setEditPositionType,
  }
}
