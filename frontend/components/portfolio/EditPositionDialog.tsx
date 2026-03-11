import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { Account } from '@/lib/api/portfolio'
import { PositionFormFields } from './PositionFormFields'
import type {
  PositionFormErrors,
  PositionType,
} from './portfolio-form-utils'
import type { FormEvent } from 'react'

interface EditPositionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  accounts: Account[] | undefined
  accountId: string
  symbol: string
  shares: string
  costBasis: string
  positionType: PositionType
  errors: PositionFormErrors
  canSubmit: boolean
  isPending: boolean
  onAccountChange: (value: string) => void
  onSymbolChange: (value: string) => void
  onSharesChange: (value: string) => void
  onCostBasisChange: (value: string) => void
  onPositionTypeChange: (value: PositionType) => void
  onUpdate: () => void
}

export function EditPositionDialog({
  open,
  onOpenChange,
  accounts,
  accountId,
  symbol,
  shares,
  costBasis,
  positionType,
  errors,
  canSubmit,
  isPending,
  onAccountChange,
  onSymbolChange,
  onSharesChange,
  onCostBasisChange,
  onPositionTypeChange,
  onUpdate,
}: EditPositionDialogProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canSubmit) {
      return
    }
    onUpdate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Position</DialogTitle>
          <DialogDescription>
            Update the details of your position.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <PositionFormFields
            idPrefix="edit-position"
            accounts={accounts}
            accountId={accountId}
            symbol={symbol}
            shares={shares}
            costBasis={costBasis}
            positionType={positionType}
            errors={errors}
            accountHint={
              !accounts?.length ? (
                <p className="text-xs text-text-muted">
                  No accounts are available for reassignment.
                </p>
              ) : undefined
            }
            onAccountChange={onAccountChange}
            onSymbolChange={onSymbolChange}
            onSharesChange={onSharesChange}
            onCostBasisChange={onCostBasisChange}
            onPositionTypeChange={onPositionTypeChange}
          />
          <DialogFooter>
            <Button type="submit" disabled={!canSubmit || isPending}>
              {isPending ? 'Updating...' : 'Update Position'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
