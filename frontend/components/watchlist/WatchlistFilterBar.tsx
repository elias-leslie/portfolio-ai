import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { WatchlistCounts } from './useWatchlistFilters'
import {
  type RiskFilter,
  SIGNAL_FILTER_LABELS,
  type SignalFilter,
  type StyleFilter,
} from './watchlistFilters'

function SignalDot({ className }: { className: string }) {
  return <span className={cn('inline-block size-2 rounded-full', className)} />
}

interface WatchlistFilterBarProps {
  totalCount: number
  signalFilter: SignalFilter
  onSignalChange: (value: SignalFilter) => void
  styleFilter: StyleFilter
  onStyleChange: (value: StyleFilter) => void
  riskFilter: RiskFilter
  onRiskChange: (value: RiskFilter) => void
  counts: WatchlistCounts
  hasActiveFilters: boolean
  onReset: () => void
}

export function WatchlistFilterBar({
  totalCount,
  signalFilter,
  onSignalChange,
  styleFilter,
  onStyleChange,
  riskFilter,
  onRiskChange,
  counts,
  hasActiveFilters,
  onReset,
}: WatchlistFilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/30 bg-surface/40 px-4 py-3 backdrop-blur-sm">
      <span className="mr-1 text-xs font-semibold uppercase tracking-widest text-text-muted/50">
        Filters
      </span>
      <Select
        value={signalFilter}
        onValueChange={(value) => onSignalChange(value as SignalFilter)}
      >
        <SelectTrigger className="w-[180px]" aria-label="Filter by signal">
          <SelectValue placeholder="Signal: All" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">
            {SIGNAL_FILTER_LABELS.all} ({totalCount})
          </SelectItem>
          <SelectItem value="BUY">
            <span className="inline-flex items-center gap-1.5">
              <SignalDot className="bg-gain" /> {SIGNAL_FILTER_LABELS.BUY} (
              {counts.signal.BUY || 0})
            </span>
          </SelectItem>
          <SelectItem value="HOLD">
            <span className="inline-flex items-center gap-1.5">
              <SignalDot className="bg-warning" /> {SIGNAL_FILTER_LABELS.HOLD} (
              {counts.signal.HOLD || 0})
            </span>
          </SelectItem>
          <SelectItem value="AVOID">
            <span className="inline-flex items-center gap-1.5">
              <SignalDot className="bg-loss" /> {SIGNAL_FILTER_LABELS.AVOID} (
              {counts.signal.AVOID || 0})
            </span>
          </SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={styleFilter}
        onValueChange={(value) => onStyleChange(value as StyleFilter)}
      >
        <SelectTrigger className="w-[160px]" aria-label="Filter by style">
          <SelectValue placeholder="Style: All" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Styles ({totalCount})</SelectItem>
          <SelectItem value="Index">
            Index ({counts.style.Index || 0})
          </SelectItem>
          <SelectItem value="Trend">
            Trend ({counts.style.Trend || 0})
          </SelectItem>
          <SelectItem value="Value">
            Value ({counts.style.Value || 0})
          </SelectItem>
          <SelectItem value="Swing">
            Swing ({counts.style.Swing || 0})
          </SelectItem>
          <SelectItem value="Event">
            Event ({counts.style.Event || 0})
          </SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={riskFilter}
        onValueChange={(value) => onRiskChange(value as RiskFilter)}
      >
        <SelectTrigger className="w-[160px]" aria-label="Filter by risk level">
          <SelectValue placeholder="Risk: All" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Risk ({totalCount})</SelectItem>
          <SelectItem value="Low">
            <span className="inline-flex items-center gap-1.5">
              <SignalDot className="bg-gain" /> Low ({counts.risk.Low || 0})
            </span>
          </SelectItem>
          <SelectItem value="Medium-Low">
            <span className="inline-flex items-center gap-1.5">
              <SignalDot className="bg-warning" /> Medium-Low (
              {counts.risk['Medium-Low'] || 0})
            </span>
          </SelectItem>
          <SelectItem value="Medium">
            <span className="inline-flex items-center gap-1.5">
              <SignalDot className="bg-warning" /> Medium (
              {counts.risk.Medium || 0})
            </span>
          </SelectItem>
          <SelectItem value="High">
            <span className="inline-flex items-center gap-1.5">
              <SignalDot className="bg-loss" /> High ({counts.risk.High || 0})
            </span>
          </SelectItem>
        </SelectContent>
      </Select>
      {hasActiveFilters ? (
        <Button type="button" variant="ghost" size="sm" onClick={onReset}>
          Reset filters
        </Button>
      ) : null}
    </div>
  )
}
