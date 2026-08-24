'use client'

import { useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { HouseholdSinkingFund } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import { useUpdateHouseholdSinkingFund } from '@/lib/hooks/useHousehold'

const STATUS_LABEL: Record<string, string> = {
  derived: 'From spending',
  declared: 'Declared',
  no_history: 'Needs an amount',
}

const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'outline'> = {
  derived: 'success',
  declared: 'outline',
  no_history: 'warning',
}

/**
 * The four funds the household chose, each priced from its own trailing spend.
 *
 * What this replaces asked for **$7,104/mo** of buffers — more than the
 * household takes home — because it treated any merchant it saw often as an
 * obligation. Every figure here prints the arithmetic that produced it, so a
 * number that looks wrong can be checked instead of argued with, and the
 * largest purchase in each window can be set aside when it was a one-off: one
 * cruise should not set a monthly travel contribution for the next year.
 */
export function SinkingFundsCard({
  funds,
  isLoading = false,
}: {
  funds: HouseholdSinkingFund[] | undefined
  isLoading?: boolean
}) {
  const updateFund = useUpdateHouseholdSinkingFund()
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [amountDraft, setAmountDraft] = useState('')
  const [noteDraft, setNoteDraft] = useState('')

  const monthlyTotal = (funds ?? []).reduce(
    (total, fund) => total + (fund.monthlyTarget ?? 0),
    0,
  )

  function openEditor(fund: HouseholdSinkingFund) {
    setAmountDraft(
      fund.overrideAmount != null
        ? String(fund.overrideAmount)
        : fund.monthlyTarget != null
          ? String(Math.round(fund.monthlyTarget))
          : '',
    )
    setNoteDraft(fund.overrideNote ?? '')
    setEditingKey(fund.key)
  }

  function saveAmount(fundKey: string) {
    const amount = Number(amountDraft.trim())
    if (!amountDraft.trim() || !Number.isFinite(amount) || amount < 0) {
      return
    }
    updateFund.mutate(
      {
        fundKey,
        payload: {
          monthlyOverride: amount,
          overrideNote: noteDraft.trim() || null,
        },
      },
      { onSuccess: () => setEditingKey(null) },
    )
  }

  return (
    <SectionCard
      variant="surface"
      title="Sinking funds"
      description={
        funds && funds.length > 0
          ? `${formatCurrencyWhole(monthlyTotal)}/mo set aside for costs that arrive in lumps.`
          : 'Costs that arrive in lumps, spread over the months before they land.'
      }
    >
      {isLoading && !funds ? (
        <p className="text-sm text-text-muted">Reading trailing spend…</p>
      ) : (
        <div className="space-y-3">
          {(funds ?? []).map((fund) => (
            <div
              key={fund.key}
              className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-text">
                    {fund.label}
                  </p>
                  <p className="mt-1 text-sm text-text-muted">
                    {fund.headline}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {fund.monthlyTarget != null ? (
                    <span className="font-mono text-lg tabular-nums text-text">
                      {formatCurrencyWhole(fund.monthlyTarget)}
                    </span>
                  ) : null}
                  <Badge variant={STATUS_VARIANT[fund.status] ?? 'outline'}>
                    {STATUS_LABEL[fund.status] ?? fund.status}
                  </Badge>
                </div>
              </div>

              <p className="mt-2 text-xs text-text-muted">{fund.derivation}</p>
              {fund.note ? (
                <p className="mt-1 text-xs text-warning">{fund.note}</p>
              ) : null}

              {editingKey === fund.key ? (
                <div className="mt-3 space-y-2 border-t border-border/30 pt-3">
                  <Input
                    value={amountDraft}
                    inputMode="decimal"
                    aria-label={`Monthly amount for ${fund.label}`}
                    placeholder="400"
                    className="h-8 text-sm"
                    onChange={(event) => setAmountDraft(event.target.value)}
                  />
                  <Input
                    value={noteDraft}
                    aria-label={`Why ${fund.label} is declared`}
                    placeholder="Why — e.g. one trip planned this year"
                    className="h-8 text-sm"
                    onChange={(event) => setNoteDraft(event.target.value)}
                  />
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => saveAmount(fund.key)}
                      disabled={updateFund.isPending}
                    >
                      Save amount
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setEditingKey(null)}
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
                    variant={
                      fund.status === 'no_history' ? 'default' : 'outline'
                    }
                    onClick={() => openEditor(fund)}
                  >
                    {fund.overrideAmount != null
                      ? 'Change amount'
                      : 'Declare an amount'}
                  </Button>
                  {fund.overrideAmount != null ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={updateFund.isPending}
                      onClick={() =>
                        updateFund.mutate({
                          fundKey: fund.key,
                          payload: {
                            monthlyOverride: null,
                            overrideNote: null,
                          },
                        })
                      }
                    >
                      Use trailing spend
                    </Button>
                  ) : null}
                  {fund.largest ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={updateFund.isPending}
                      onClick={() =>
                        updateFund.mutate({
                          fundKey: fund.key,
                          payload: { dropLargest: !fund.largestDropped },
                        })
                      }
                    >
                      {fund.largestDropped
                        ? `Count ${fund.largest.merchant} ${formatCurrencyWhole(fund.largest.amount)} again`
                        : `Set aside ${fund.largest.merchant} ${formatCurrencyWhole(fund.largest.amount)}`}
                    </Button>
                  ) : null}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  )
}
