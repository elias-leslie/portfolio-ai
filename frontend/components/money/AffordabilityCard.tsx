'use client'

import { Badge } from '@/components/ui/badge'
import type { HouseholdAffordability } from '@/lib/api/household'
import { formatCurrencyWhole, formatEnumLabel } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import { decisionBadgeVariant, shortDate } from './overview-helpers'

export interface AffordabilityCardProps {
  affordability: HouseholdAffordability | null | undefined
  isLoading: boolean
  /**
   * Which inputs behind the figure are not fresh, each naming the input rather
   * than the system. "Stale account data" tells the reader nothing they can act
   * on; "cash and card balances need a refresh" tells them where to go.
   */
  caveats?: string[]
}

const TONE: Record<string, string> = {
  estimate: 'border-border/35 bg-surface-muted/20',
  tight: 'border-warning/40 bg-warning/5',
  hold: 'border-loss/40 bg-loss/5',
}

const VALUE_TONE: Record<string, string> = {
  hold: 'text-loss',
}

interface LedgerLine {
  label: string
  amount: number
  subtract: boolean
}

/**
 * "Can we actually spend this?" — answered on the screen where the month is
 * reviewed, not one tab away on the overview.
 *
 * The card shows the whole subtraction rather than a single confident figure,
 * because the number it replaced was $1,283 while $30k sat in the CMA and
 * $17k was owed on three cards, and nothing on screen let the household see
 * which of those the figure had counted. Every line here is money that exists
 * or money that is owed; inputs the system does not have are named instead of
 * being treated as zero.
 *
 * The status word and the headline come from the server. This screen and the
 * overview read the same grade of the same dollar figure — the review exists
 * because two surfaces answering one question differently is the whole problem.
 */
export function AffordabilityCard({
  affordability,
  isLoading,
  caveats = [],
}: AffordabilityCardProps) {
  if (!affordability) {
    return (
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-sm font-semibold text-text">Free to spend</p>
        <p className="mt-1 text-sm text-text-muted">
          {isLoading
            ? 'Adding up cash and commitments…'
            : 'Not enough cash and commitment data to answer this yet.'}
        </p>
      </div>
    )
  }

  // A caveat downgrades the grade but never hides the number or the sentence
  // that explains it: showing $11,941 while suppressing what it means is the
  // worst of both, and it is what the old card did.
  const status = caveats.length > 0 ? 'review' : affordability.status
  const lines: LedgerLine[] = [
    {
      label: 'Cash on hand',
      amount: affordability.cashOnHand,
      subtract: false,
    },
    {
      label: `Bills due through ${shortDate(affordability.billsDueThrough)}`,
      amount: affordability.billsDue,
      subtract: true,
    },
    {
      label: 'Essentials still to come',
      amount: affordability.remainingEssentials,
      subtract: true,
    },
    {
      label: 'Owed on cards',
      amount: affordability.cardBalances,
      subtract: true,
    },
  ]
  if (affordability.committedFunds > 0) {
    lines.push({
      label: 'Committed to sinking funds',
      amount: affordability.committedFunds,
      subtract: true,
    })
  }

  return (
    <div
      className={cn('rounded-2xl border p-4', TONE[status] ?? TONE.estimate)}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-text">Free to spend</p>
        <Badge variant={decisionBadgeVariant(status)}>
          {formatEnumLabel(status)}
        </Badge>
      </div>
      <p
        className={cn(
          'mt-2 text-2xl font-semibold tabular-nums',
          VALUE_TONE[status] ?? 'text-text',
        )}
      >
        {formatCurrencyWhole(affordability.freeToSpend)}
      </p>
      <p className="mt-1 text-sm text-text-muted">{affordability.headline}</p>
      {caveats.map((caveat) => (
        <p key={caveat} className="mt-1 text-xs text-warning">
          {caveat}
        </p>
      ))}

      <dl className="mt-3 space-y-1 border-t border-border/30 pt-3 text-xs">
        {lines.map((line) => (
          <div
            key={line.label}
            className="flex items-baseline justify-between gap-3"
          >
            <dt className="text-text-muted">
              {line.subtract ? 'less ' : ''}
              {line.label}
            </dt>
            <dd className="font-mono tabular-nums text-text-muted">
              {line.subtract ? '−' : ''}
              {formatCurrencyWhole(line.amount)}
            </dd>
          </div>
        ))}
        <div className="flex items-baseline justify-between gap-3 border-t border-border/30 pt-1 font-medium">
          <dt className="text-text">Free to spend</dt>
          <dd
            className={cn(
              'font-mono tabular-nums',
              VALUE_TONE[status] ?? 'text-text',
            )}
          >
            {formatCurrencyWhole(affordability.freeToSpend)}
          </dd>
        </div>
      </dl>

      <p className="mt-2 text-xs text-text-muted/80">
        {affordability.essentialsBasis}
      </p>
      {affordability.missingInputs.length > 0 ? (
        <p className="mt-1 text-xs text-text-muted/80">
          Not yet counted:{' '}
          {affordability.missingInputs
            .map((input) => formatEnumLabel(input).toLowerCase())
            .join(', ')}
          .
        </p>
      ) : null}
    </div>
  )
}
