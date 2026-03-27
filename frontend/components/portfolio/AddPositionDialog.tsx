'use client'

import { PositionFormFields } from '@/components/portfolio/PositionFormFields'
import {
  type PositionType,
  getPositionFormErrors,
  isPositionFormValid,
  normalizeSymbol,
} from '@/components/portfolio/portfolio-form-utils'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useAccounts, useAddPosition } from '@/lib/hooks/usePortfolio'
import { useState } from 'react'

interface AddPositionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Pre-selected account when dialog opens. Change this + open to reset form. */
  defaultAccountId?: string
}

export function AddPositionDialog({
  open,
  onOpenChange,
  defaultAccountId = '',
}: AddPositionDialogProps) {
  const addPosition = useAddPosition()
  const { data: accounts, isLoading: accountsLoading } = useAccounts()

  const [accountId, setAccountId] = useState(defaultAccountId)
  const [symbol, setSymbol] = useState('')
  const [shares, setShares] = useState('')
  const [costBasis, setCostBasis] = useState('')
  const [positionType, setPositionType] = useState<PositionType>('long')
  const [submitAttempted, setSubmitAttempted] = useState(false)

  const positionFormErrors = getPositionFormErrors({ accountId, symbol, shares, costBasis })
  const canSubmit = isPositionFormValid(positionFormErrors)

  const resetForm = (nextAccountId = '') => {
    setAccountId(nextAccountId)
    setSymbol('')
    setShares('')
    setCostBasis('')
    setPositionType('long')
    setSubmitAttempted(false)
  }

  const handleOpenChange = (next: boolean) => {
    onOpenChange(next)
    if (!next) {
      resetForm(accounts?.length === 1 ? accounts[0].id : '')
    }
  }

  const handleSubmit = () => {
    setSubmitAttempted(true)
    if (!canSubmit) return

    addPosition.mutate(
      {
        accountId,
        symbol: normalizeSymbol(symbol),
        shares: parseFloat(shares),
        costBasis: parseFloat(costBasis),
        positionType,
      },
      {
        onSuccess: () => {
          handleOpenChange(false)
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Position</DialogTitle>
          <DialogDescription>
            Add a new position to your portfolio. Enter the live holding details below.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            handleSubmit()
          }}
        >
          <PositionFormFields
            idPrefix="add-position"
            accounts={accounts}
            accountsLoading={accountsLoading}
            accountId={accountId}
            symbol={symbol}
            shares={shares}
            costBasis={costBasis}
            positionType={positionType}
            errors={submitAttempted ? positionFormErrors : undefined}
            accountHint={
              !accounts?.length && !accountsLoading ? (
                <p className="text-xs text-warning">
                  Create an account first so the position is tracked in the right tax and ownership
                  bucket.
                </p>
              ) : undefined
            }
            onAccountChange={setAccountId}
            onSymbolChange={setSymbol}
            onSharesChange={setShares}
            onCostBasisChange={setCostBasis}
            onPositionTypeChange={setPositionType}
          />
          <DialogFooter>
            <Button
              type="submit"
              disabled={!canSubmit || addPosition.isPending}
              aria-busy={addPosition.isPending}
            >
              {addPosition.isPending ? 'Adding...' : 'Add Position'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
