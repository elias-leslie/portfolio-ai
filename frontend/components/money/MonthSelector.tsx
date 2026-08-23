'use client'

import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { formatFullMonthLabel } from './budget-helpers'

export interface MonthSelectorProps {
  /** Every month the household has a ledger for, oldest first. */
  availableMonths: string[]
  month: string | null
  onChange: (month: string) => void
  isMonthToDate?: boolean
  /** e.g. "through day 23 of 31" — shown only while the month is still running. */
  basisLabel?: string
  disabled?: boolean
}

/**
 * Pick the month to review.
 *
 * Replaces the 1M/3M/6M/12M chips (D3). Those chips each divided by their own
 * coverage while admitting their own account set, so the same ledger answered
 * "what did we spend" four different ways. A calendar month cannot: it starts on
 * the 1st and ends on the last day, and it is the same month on every screen.
 */
export function MonthSelector({
  availableMonths,
  month,
  onChange,
  isMonthToDate = false,
  basisLabel,
  disabled = false,
}: MonthSelectorProps) {
  const index = month == null ? -1 : availableMonths.indexOf(month)
  const hasOlder = index > 0
  const hasNewer = index >= 0 && index < availableMonths.length - 1
  // The months arrive with the first payload, so the select is mounted only once
  // it has a real value -- mounting it empty and filling it in later makes React
  // switch it from uncontrolled to controlled mid-life.
  const isReady = month != null && availableMonths.length > 0

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        type="button"
        size="sm"
        variant="outline"
        aria-label="Previous month"
        disabled={disabled || !hasOlder}
        onClick={() => hasOlder && onChange(availableMonths[index - 1])}
      >
        <ChevronLeftIcon className="size-4" />
      </Button>
      {isReady ? (
        <Select value={month} onValueChange={onChange} disabled={disabled}>
          <SelectTrigger size="sm" className="min-w-[11rem]" aria-label="Month">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[...availableMonths].reverse().map((option) => (
              <SelectItem key={option} value={option}>
                {formatFullMonthLabel(option)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <span className="min-w-[11rem] rounded-md border border-border bg-surface/80 px-3 py-1.5 text-sm text-text-muted">
          Loading months…
        </span>
      )}
      <Button
        type="button"
        size="sm"
        variant="outline"
        aria-label="Next month"
        disabled={disabled || !hasNewer}
        onClick={() => hasNewer && onChange(availableMonths[index + 1])}
      >
        <ChevronRightIcon className="size-4" />
      </Button>
      {isMonthToDate ? (
        <Badge variant="outline">
          Month to date{basisLabel ? ` · ${basisLabel}` : ''}
        </Badge>
      ) : null}
    </div>
  )
}
