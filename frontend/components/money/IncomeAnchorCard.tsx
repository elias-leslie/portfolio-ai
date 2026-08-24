'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { HouseholdIncomeAnchor } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import { useUpdateHouseholdProfile } from '@/lib/hooks/useHousehold'
import { cn } from '@/lib/utils'

const TONE: Record<string, string> = {
  measured: 'border-border/35 bg-surface-muted/20',
  declared: 'border-primary/40 bg-primary/5',
  insufficient_history: 'border-warning/40 bg-warning/5',
}

const STATUS_LABEL: Record<string, string> = {
  measured: 'Measured',
  declared: 'Declared',
  insufficient_history: 'Not measurable',
}

const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'outline'> = {
  measured: 'success',
  declared: 'outline',
  insufficient_history: 'warning',
}

/**
 * What a normal month brings in — the number every cap in Phase 3 is priced off.
 *
 * The months behind it are listed rather than summarised, because the household
 * has been asked to trust a $6,283/mo take-home target that sits above what
 * actually arrives in most months. A median of three complete months can be
 * checked against a bank statement in under a minute; a figure with no working
 * shown cannot be checked at all.
 *
 * A declared anchor ("SummitFlow starts next month") outranks the measurement,
 * but never replaces it on screen: both are shown, with the day the declaration
 * was made, so an anchor that stopped being true is visible instead of silent.
 */
export function IncomeAnchorCard({
  anchor,
  isLoading = false,
}: {
  anchor: HouseholdIncomeAnchor | null | undefined
  isLoading?: boolean
}) {
  const updateProfile = useUpdateHouseholdProfile()
  const [editing, setEditing] = useState(false)
  const [amountDraft, setAmountDraft] = useState('')
  const [noteDraft, setNoteDraft] = useState('')

  if (!anchor) {
    return (
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-sm font-semibold text-text">Income anchor</p>
        <p className="mt-1 text-sm text-text-muted">
          {isLoading
            ? 'Reading the last complete months of income…'
            : 'No income history is available to anchor the plan yet.'}
        </p>
      </div>
    )
  }

  function openEditor() {
    setAmountDraft(
      anchor?.overrideAmount != null
        ? String(anchor.overrideAmount)
        : anchor?.medianMonthlyIncome != null
          ? String(anchor.medianMonthlyIncome)
          : '',
    )
    setNoteDraft(anchor?.overrideNote ?? '')
    setEditing(true)
  }

  function saveOverride() {
    const amount = Number(amountDraft.trim())
    if (!amountDraft.trim() || !Number.isFinite(amount) || amount <= 0) {
      return
    }
    updateProfile.mutate(
      {
        incomeAnchorOverride: amount,
        // Dated on the day it is declared. An undated anchor cannot be told
        // apart from one that stopped being true months ago.
        incomeAnchorOverrideSetOn: new Date().toISOString().slice(0, 10),
        incomeAnchorOverrideNote: noteDraft.trim() || null,
      },
      { onSuccess: () => setEditing(false) },
    )
  }

  function clearOverride() {
    updateProfile.mutate({
      incomeAnchorOverride: null,
      incomeAnchorOverrideSetOn: null,
      incomeAnchorOverrideNote: null,
    })
  }

  return (
    <div
      className={cn(
        'rounded-2xl border p-4',
        TONE[anchor.status] ?? TONE.measured,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-text">Income anchor</p>
        <Badge variant={STATUS_VARIANT[anchor.status] ?? 'outline'}>
          {STATUS_LABEL[anchor.status] ?? anchor.status}
        </Badge>
      </div>

      {/* No figure rather than a $0 that reads like an answer: the headline
          below says what is missing. */}
      {anchor.monthlyIncome != null ? (
        <p className="mt-2 text-2xl font-semibold tabular-nums text-text">
          {formatCurrencyWhole(anchor.monthlyIncome)}
        </p>
      ) : null}
      <p className="mt-1 text-sm text-text-muted">{anchor.headline}</p>
      <p className="mt-1 text-xs text-text-muted">{anchor.detail}</p>

      {anchor.overrideStale && anchor.overrideStaleDetail ? (
        <p className="mt-2 text-xs text-warning">
          {anchor.overrideStaleDetail}
        </p>
      ) : null}

      {anchor.monthsUsed.length > 0 ? (
        <dl className="mt-3 space-y-1 border-t border-border/30 pt-3 text-xs">
          {anchor.monthsUsed.map((month) => (
            <div
              key={month.month}
              className="flex items-baseline justify-between gap-3"
            >
              <dt className="text-text-muted">
                {month.label}
                {month.isMedian ? (
                  <span className="ml-2 text-[10px] uppercase tracking-wide text-text-muted">
                    median
                  </span>
                ) : null}
              </dt>
              <dd
                className={cn(
                  'font-mono tabular-nums',
                  month.isMedian ? 'text-text' : 'text-text-muted',
                )}
              >
                {formatCurrencyWhole(month.amount)}
              </dd>
            </div>
          ))}
          {anchor.status === 'declared' &&
          anchor.medianMonthlyIncome != null ? (
            <div className="flex items-baseline justify-between gap-3 border-t border-border/30 pt-1">
              <dt className="text-text-muted">Measured median</dt>
              <dd className="font-mono tabular-nums text-text-muted">
                {formatCurrencyWhole(anchor.medianMonthlyIncome)}
              </dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {anchor.profileTargetDetail ? (
        <p className="mt-3 text-xs text-text-muted">
          {anchor.profileTargetDetail}
        </p>
      ) : null}

      {editing ? (
        <div className="mt-3 space-y-2 border-t border-border/30 pt-3">
          <Input
            value={amountDraft}
            inputMode="decimal"
            aria-label="Declared monthly income"
            placeholder="9000"
            className="h-8 text-sm"
            onChange={(event) => setAmountDraft(event.target.value)}
          />
          <Input
            value={noteDraft}
            aria-label="Why this anchor was declared"
            placeholder="Why — e.g. new contract starts in September"
            className="h-8 text-sm"
            onChange={(event) => setNoteDraft(event.target.value)}
          />
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              onClick={saveOverride}
              disabled={updateProfile.isPending}
            >
              Save anchor
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setEditing(false)}
              disabled={updateProfile.isPending}
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
            variant="outline"
            onClick={openEditor}
          >
            {anchor.overrideAmount != null
              ? 'Change anchor'
              : 'Declare an anchor'}
          </Button>
          {anchor.overrideAmount != null ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={clearOverride}
              disabled={updateProfile.isPending}
            >
              Use the measured median
            </Button>
          ) : null}
        </div>
      )}
    </div>
  )
}
