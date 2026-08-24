'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { HouseholdSavingsPlan } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import { useUpdateHouseholdProfile } from '@/lib/hooks/useHousehold'
import { cn } from '@/lib/utils'

const TONE: Record<string, string> = {
  active: 'border-border/35 bg-surface-muted/20',
  paused: 'border-border/35 bg-surface-muted/20',
  restart_due: 'border-primary/40 bg-primary/5',
  undeclared: 'border-warning/40 bg-warning/5',
}

const STATUS_LABEL: Record<string, string> = {
  active: 'Active',
  paused: 'Paused',
  restart_due: 'Time to resume',
  undeclared: 'Not decided',
}

const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'outline'> = {
  active: 'success',
  paused: 'outline',
  restart_due: 'success',
  undeclared: 'warning',
}

type Editor = 'none' | 'amount' | 'pause'

/**
 * Whether the household is saving on purpose — and if not, what changes that.
 *
 * The state it replaces was a $0 monthly target that reported the household as
 * keeping up, which is a pass awarded for having no plan. Pausing is now
 * something you declare, with the day you declared it and the income level that
 * ends it; the card watches the income anchor and says when that level is
 * reached, so a pause taken during unemployment cannot quietly become the plan.
 */
export function SavingsPlanCard({
  plan,
  isLoading = false,
}: {
  plan: HouseholdSavingsPlan | null | undefined
  isLoading?: boolean
}) {
  const updateProfile = useUpdateHouseholdProfile()
  const [editor, setEditor] = useState<Editor>('none')
  const [amountDraft, setAmountDraft] = useState('')
  const [thresholdDraft, setThresholdDraft] = useState('')
  const [reasonDraft, setReasonDraft] = useState('')

  if (!plan) {
    return (
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-sm font-semibold text-text">Saving</p>
        <p className="mt-1 text-sm text-text-muted">
          {isLoading
            ? 'Reading the savings plan…'
            : 'No savings plan is on record yet.'}
        </p>
      </div>
    )
  }

  function openAmountEditor() {
    setAmountDraft(plan?.monthlyTarget ? String(plan.monthlyTarget) : '')
    setEditor('amount')
  }

  function openPauseEditor() {
    setThresholdDraft(
      plan?.restartIncomeThreshold != null
        ? String(plan.restartIncomeThreshold)
        : plan?.anchorMonthlyIncome != null
          ? String(Math.round(plan.anchorMonthlyIncome))
          : '',
    )
    setReasonDraft(plan?.pauseReason ?? '')
    setEditor('pause')
  }

  function saveAmount() {
    const amount = Number(amountDraft.trim())
    if (!amountDraft.trim() || !Number.isFinite(amount) || amount <= 0) {
      return
    }
    // Naming an amount is how a pause ends: the two states cannot both be on.
    updateProfile.mutate(
      {
        monthlySavingsTarget: amount,
        savingsPausedOn: null,
        savingsPauseReason: null,
        savingsRestartIncomeThreshold: null,
      },
      { onSuccess: () => setEditor('none') },
    )
  }

  function savePause() {
    const threshold = Number(thresholdDraft.trim())
    if (
      !thresholdDraft.trim() ||
      !Number.isFinite(threshold) ||
      threshold <= 0
    ) {
      return
    }
    updateProfile.mutate(
      {
        savingsPausedOn: new Date().toISOString().slice(0, 10),
        savingsPauseReason: reasonDraft.trim() || null,
        savingsRestartIncomeThreshold: threshold,
        monthlySavingsTarget: 0,
      },
      { onSuccess: () => setEditor('none') },
    )
  }

  return (
    <div
      className={cn('rounded-2xl border p-4', TONE[plan.status] ?? TONE.active)}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-text">Saving</p>
        <Badge variant={STATUS_VARIANT[plan.status] ?? 'outline'}>
          {STATUS_LABEL[plan.status] ?? plan.status}
        </Badge>
      </div>

      {plan.status === 'active' && plan.monthlyTarget != null ? (
        <p className="mt-2 text-2xl font-semibold tabular-nums text-text">
          {formatCurrencyWhole(plan.monthlyTarget)}
        </p>
      ) : null}
      <p className="mt-2 text-sm text-text-muted">{plan.headline}</p>
      <p className="mt-1 text-xs text-text-muted">{plan.detail}</p>

      {editor === 'amount' ? (
        <div className="mt-3 space-y-2 border-t border-border/30 pt-3">
          <Input
            value={amountDraft}
            inputMode="decimal"
            aria-label="Monthly savings amount"
            placeholder="500"
            className="h-8 text-sm"
            onChange={(event) => setAmountDraft(event.target.value)}
          />
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              onClick={saveAmount}
              disabled={updateProfile.isPending}
            >
              Save amount
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setEditor('none')}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : editor === 'pause' ? (
        <div className="mt-3 space-y-2 border-t border-border/30 pt-3">
          <Input
            value={thresholdDraft}
            inputMode="decimal"
            aria-label="Monthly income that restarts saving"
            placeholder="8000"
            className="h-8 text-sm"
            onChange={(event) => setThresholdDraft(event.target.value)}
          />
          <Input
            value={reasonDraft}
            aria-label="Why saving is paused"
            placeholder="Why — e.g. on unemployment until the contract starts"
            className="h-8 text-sm"
            onChange={(event) => setReasonDraft(event.target.value)}
          />
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              onClick={savePause}
              disabled={updateProfile.isPending}
            >
              Pause saving
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setEditor('none')}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-border/30 pt-3">
          <Button
            type="button"
            size="sm"
            variant={plan.status === 'active' ? 'outline' : 'default'}
            onClick={openAmountEditor}
          >
            {plan.status === 'active'
              ? 'Change amount'
              : 'Set a monthly amount'}
          </Button>
          {plan.status === 'active' || plan.status === 'undeclared' ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={openPauseEditor}
              disabled={updateProfile.isPending}
            >
              Pause saving
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={openPauseEditor}
              disabled={updateProfile.isPending}
            >
              Change the restart trigger
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
