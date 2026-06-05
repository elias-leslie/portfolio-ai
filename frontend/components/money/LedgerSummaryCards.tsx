import { formatCurrency } from '@/lib/formatters'
import { formatLedgerDate } from './ledger-helpers'

interface LedgerSummaryCardsProps {
  timeframeLabel?: string | null
  startDate?: string | null
  endDate?: string | null
  visibleDebitTotal: number
  visibleCreditTotal: number
  visibleNetMovement: number
  filteredCount: number
  includedCount: number
  excludedCount: number
}

export function LedgerSummaryCards({
  timeframeLabel,
  startDate,
  endDate,
  visibleDebitTotal,
  visibleCreditTotal,
  visibleNetMovement,
  filteredCount,
  includedCount,
  excludedCount,
}: LedgerSummaryCardsProps) {
  return (
    <div className="grid gap-3 xl:grid-cols-5">
      <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
        <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
          Window
        </p>
        <p className="mt-2 text-base font-semibold text-text">
          {timeframeLabel ?? 'Loading'}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          {startDate
            ? `${formatLedgerDate(startDate)} to ${formatLedgerDate(endDate)}`
            : 'Full ledger history'}
        </p>
      </div>
      <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
        <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
          Debits
        </p>
        <p className="mt-2 text-base font-semibold tabular-nums text-text">
          {formatCurrency(visibleDebitTotal, { decimals: 2 })}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          Visible debits in current view
        </p>
      </div>
      <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
        <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
          Credits
        </p>
        <p className="mt-2 text-base font-semibold tabular-nums text-text">
          {formatCurrency(visibleCreditTotal, { decimals: 2 })}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          Visible credits in current view
        </p>
      </div>
      <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
        <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
          Net
        </p>
        <p className="mt-2 text-base font-semibold tabular-nums text-text">
          {formatCurrency(Math.abs(visibleNetMovement), { decimals: 2 })}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          {visibleNetMovement >= 0 ? 'Net debit' : 'Net credit'}
        </p>
      </div>
      <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
        <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
          Rows
        </p>
        <p className="mt-2 text-base font-semibold text-text">
          {filteredCount}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          {includedCount} counted · {excludedCount} excluded
        </p>
      </div>
    </div>
  )
}
