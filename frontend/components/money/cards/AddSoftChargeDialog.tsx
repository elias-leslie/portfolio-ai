'use client'

import { useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { SoftCharge } from '@/lib/api/cards'
import { formatCurrency } from '@/lib/formatters'
import { useCreateSoftCharge, useDeleteSoftCharge } from '@/lib/hooks/useCards'
import { formatShortDate } from './cards-helpers'

function statusBadgeVariant(status: string) {
  if (status === 'matched') return 'success' as const
  if (status === 'voided') return 'secondary' as const
  return 'warning' as const
}

export function AddSoftChargeDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [merchant, setMerchant] = useState('')
  const [category, setCategory] = useState('')
  const [receipt, setReceipt] = useState<File | null>(null)
  const createSoftCharge = useCreateSoftCharge()

  const reset = () => {
    setAmount('')
    setDescription('')
    setMerchant('')
    setCategory('')
    setReceipt(null)
  }

  const parsedAmount = Number(amount)
  const canSubmit =
    Number.isFinite(parsedAmount) &&
    parsedAmount > 0 &&
    description.trim().length > 0 &&
    !createSoftCharge.isPending

  const handleSubmit = () => {
    if (!canSubmit) return
    createSoftCharge.mutate(
      {
        amount: parsedAmount,
        description: description.trim(),
        merchant: merchant.trim() || undefined,
        category: category.trim() || undefined,
        receipt,
      },
      {
        onSuccess: () => {
          reset()
          onOpenChange(false)
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Log a soft charge</DialogTitle>
          <DialogDescription>
            Phone-entered provisional charge. It counts toward the budget
            immediately and is matched to the bank transaction when it posts.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="soft-charge-amount">Amount</Label>
            <Input
              id="soft-charge-amount"
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              placeholder="42.50"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="soft-charge-description">Description</Label>
            <Input
              id="soft-charge-description"
              placeholder="Lunch with the team"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="soft-charge-merchant">Merchant (optional)</Label>
              <Input
                id="soft-charge-merchant"
                placeholder="Chipotle"
                value={merchant}
                onChange={(event) => setMerchant(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="soft-charge-category">Category (optional)</Label>
              <Input
                id="soft-charge-category"
                placeholder="Dining"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="soft-charge-receipt">
              Receipt photo (optional)
            </Label>
            <Input
              id="soft-charge-receipt"
              type="file"
              accept="image/*,.pdf"
              capture="environment"
              onChange={(event) => setReceipt(event.target.files?.[0] ?? null)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button type="button" onClick={handleSubmit} disabled={!canSubmit}>
            {createSoftCharge.isPending ? 'Logging…' : 'Log charge'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function SoftChargesSection({
  softCharges,
  onAdd,
}: {
  softCharges: SoftCharge[]
  onAdd: () => void
}) {
  const deleteSoftCharge = useDeleteSoftCharge()

  return (
    <SectionCard
      variant="surface"
      title="Soft charges"
      description="Provisional phone-entered charges; they count toward the budget now and reconcile against Plaid when the transaction posts."
      actions={
        <Button type="button" size="sm" onClick={onAdd}>
          Log soft charge
        </Button>
      }
    >
      {softCharges.length === 0 ? (
        <p className="text-sm text-text-muted">
          No soft charges logged. Use “Log soft charge” right after a card swipe
          so the budget never lags reality.
        </p>
      ) : (
        <ul className="space-y-2">
          {softCharges.map((charge) => (
            <li
              key={charge.id}
              className="flex flex-col gap-1.5 rounded-2xl border border-border/40 bg-surface-muted/10 px-4 py-2.5 md:flex-row md:items-center md:justify-between"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium tabular-nums text-text">
                  {formatCurrency(charge.amount)}
                </span>
                <span className="text-sm text-text">{charge.description}</span>
                {charge.merchant ? (
                  <span className="text-xs text-text-muted">
                    {charge.merchant}
                  </span>
                ) : null}
                <Badge variant={statusBadgeVariant(charge.status)}>
                  {charge.status}
                </Badge>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-text-muted">
                  {formatShortDate(charge.occurredAt)}
                </span>
                {charge.status !== 'matched' ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="text-text-muted hover:text-destructive"
                    onClick={() => deleteSoftCharge.mutate(charge.id)}
                    disabled={deleteSoftCharge.isPending}
                  >
                    Delete
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}
