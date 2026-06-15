'use client'

import type { Dispatch, SetStateAction } from 'react'
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
import { Textarea } from '@/components/ui/textarea'
import type { HouseholdSpendingCategory } from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { OwnerPickerField } from './OwnerPickerField'
import { buildOwnerOptions } from './owner-options'

export interface BudgetDialogProps {
  selectedCategory: HouseholdSpendingCategory | null
  onClose: () => void
  budgetInput: string
  setBudgetInput: Dispatch<SetStateAction<string>>
  noteInput: string
  setNoteInput: Dispatch<SetStateAction<string>>
  ownerInput: string
  setOwnerInput: Dispatch<SetStateAction<string>>
  disabled: boolean
  setDisabled: Dispatch<SetStateAction<boolean>>
  confirmPending: boolean
  onSaveManual: () => void
  onAcceptSuggested: () => void
}

export function BudgetDialog({
  selectedCategory,
  onClose,
  budgetInput,
  setBudgetInput,
  noteInput,
  setNoteInput,
  ownerInput,
  setOwnerInput,
  disabled,
  setDisabled,
  confirmPending,
  onSaveManual,
  onAcceptSuggested,
}: BudgetDialogProps) {
  return (
    <Dialog
      open={selectedCategory != null}
      onOpenChange={(open) => {
        if (!open) {
          onClose()
        }
      }}
    >
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {selectedCategory
              ? `${selectedCategory.category} budget`
              : 'Budget'}
          </DialogTitle>
          <DialogDescription>
            Save a manual cap, accept a suggested cap, add context for Jenny, or
            hide the category when it should stay out of the budget view.
          </DialogDescription>
        </DialogHeader>

        {selectedCategory ? (
          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Observed monthly spend
                </p>
                <p className="mt-3 text-xl font-semibold text-text">
                  {formatCurrency(selectedCategory.averageMonthlySpend, {
                    decimals: 0,
                  })}
                </p>
              </div>
              <div className="rounded-2xl border border-warning/30 bg-warning/8 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-warning">
                  Suggested cap
                </p>
                <p className="mt-3 text-xl font-semibold text-text">
                  {formatCurrency(selectedCategory.foundMonthlyBudget ?? null, {
                    decimals: 0,
                  })}
                </p>
                <p className="mt-2 text-sm text-text-muted">
                  Derived from recent transaction evidence.
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Type
                </p>
                <p className="mt-3 text-xl font-semibold text-text">
                  {formatEnumLabel(selectedCategory.essentiality)}
                </p>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-[0.8fr_1.2fr]">
              <div className="space-y-2">
                <Label htmlFor="category-budget-input">Monthly budget</Label>
                <Input
                  id="category-budget-input"
                  inputMode="decimal"
                  value={budgetInput}
                  onChange={(event) => setBudgetInput(event.target.value)}
                  placeholder="750"
                />
                <OwnerPickerField
                  id="category-budget-owner"
                  label="Default owner"
                  value={ownerInput}
                  onChange={setOwnerInput}
                  options={buildOwnerOptions([ownerInput])}
                  placeholder="Mariana, Elias, Family..."
                  description="Used for owner spend views when item-level ownership is not set."
                  className="space-y-2"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="category-budget-note">
                  Note for Jenny / agents
                </Label>
                <Textarea
                  id="category-budget-note"
                  value={noteInput}
                  onChange={(event) => setNoteInput(event.target.value)}
                  placeholder="Why this cap matters, exceptions, or why this category should stay disabled."
                  rows={4}
                />
              </div>
            </div>

            <div className="flex items-center justify-between rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
              <div>
                <p className="text-sm font-semibold text-text">
                  Hide this category
                </p>
                <p className="mt-1 text-sm text-text-muted">
                  Disabled categories stay out of the budget table. A note is
                  required.
                </p>
              </div>
              <Button
                type="button"
                variant={disabled ? 'default' : 'outline'}
                onClick={() => setDisabled((current) => !current)}
              >
                {disabled ? 'Hidden' : 'Visible'}
              </Button>
            </div>
          </div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          {selectedCategory?.foundMonthlyBudget != null ? (
            <Button
              type="button"
              variant="outline"
              onClick={onAcceptSuggested}
              disabled={confirmPending}
            >
              Accept suggested cap
            </Button>
          ) : null}
          <Button
            type="button"
            onClick={onSaveManual}
            disabled={confirmPending}
          >
            {confirmPending ? 'Saving...' : 'Save budget'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
