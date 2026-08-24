'use client'

import { useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import type { HouseholdSpendVariance } from '@/lib/api/household'
import { formatCurrencyWhole, formatPercent } from '@/lib/formatters'
import { cn } from '@/lib/utils'

export interface WhatChangedCardProps {
  variance: HouseholdSpendVariance | null | undefined
}

function changeTone(value: number) {
  if (Math.abs(value) < 1) return 'text-text-muted'
  return value > 0 ? 'text-loss' : 'text-gain'
}

function signedCurrency(value: number) {
  const magnitude = formatCurrencyWhole(Math.abs(value))
  if (Math.abs(value) < 1) return magnitude
  return value > 0 ? `+${magnitude}` : `−${magnitude}`
}

/**
 * "We were over because of this one purchase, but everything else was under."
 *
 * The month total cannot say that, and saying only the total turns a household
 * that bought an air conditioner into a household that overspent. So both
 * readings are shown: the headline change, and the same comparison with the
 * one-time purchases set aside on **both** sides.
 *
 * The driver list is measured on the everyday rows only. A category whose entire
 * movement is the purchase that was just set aside is not a category that
 * changed its habits, and naming it here would contradict the line above it.
 */
export function WhatChangedCard({ variance }: WhatChangedCardProps) {
  const [excludeOneTime, setExcludeOneTime] = useState(false)

  if (!variance) {
    return null
  }

  const hasOneTime =
    variance.oneTimeMonthSpend > 0 || variance.oneTimeComparatorSpend > 0
  const shownChange = excludeOneTime ? variance.everydayChange : variance.change
  const shownMonth = excludeOneTime
    ? variance.everydayMonthSpend
    : variance.monthSpend
  const shownComparator = excludeOneTime
    ? variance.everydayComparatorSpend
    : variance.comparatorSpend

  return (
    <SectionCard
      variant="surface"
      title="What changed"
      description={`This month against ${variance.comparatorLabel}.`}
      actions={
        hasOneTime ? (
          <Button
            type="button"
            size="sm"
            variant={excludeOneTime ? 'default' : 'outline'}
            onClick={() => setExcludeOneTime((current) => !current)}
          >
            {excludeOneTime ? 'Including one-time' : 'Excluding one-time'}
          </Button>
        ) : null
      }
    >
      <p className={cn('text-lg font-semibold', changeTone(shownChange))}>
        {signedCurrency(shownChange)}
      </p>
      <p className="mt-1 text-sm text-text-muted">
        {formatCurrencyWhole(shownMonth)} against{' '}
        {formatCurrencyWhole(shownComparator)}
        {excludeOneTime ? ', one-time purchases set aside on both sides.' : '.'}
      </p>
      <p className="mt-3 text-sm text-text">{variance.headline}</p>
      <p className="mt-1 text-sm text-text-muted">{variance.detail}</p>

      {variance.drivers.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {variance.drivers.map((driver) => (
            <li
              key={driver.category}
              className="flex flex-wrap items-baseline justify-between gap-2 border-t border-border/20 pt-2 text-sm"
            >
              <span className="font-medium text-text">{driver.category}</span>
              <span className="flex items-baseline gap-3">
                <span className="text-xs text-text-muted">
                  {formatCurrencyWhole(driver.comparatorSpend)} →{' '}
                  {formatCurrencyWhole(driver.monthSpend)}
                </span>
                <span
                  className={cn(
                    'font-mono tabular-nums',
                    changeTone(driver.contribution),
                  )}
                >
                  {signedCurrency(driver.contribution)}
                </span>
                <span className="w-12 text-right text-xs text-text-muted">
                  {formatPercent(driver.shareOfChange * 100, { decimals: 0 })}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-text-muted">
          No category moved enough to explain the difference on its own.
        </p>
      )}
    </SectionCard>
  )
}
