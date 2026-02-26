import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { WatchlistCounts } from './useWatchlistFilters'
import type { RiskFilter, SignalFilter, StyleFilter } from './watchlistFilters'

interface WatchlistFilterBarProps {
  totalCount: number
  signalFilter: SignalFilter
  onSignalChange: (value: SignalFilter) => void
  styleFilter: StyleFilter
  onStyleChange: (value: StyleFilter) => void
  riskFilter: RiskFilter
  onRiskChange: (value: RiskFilter) => void
  counts: WatchlistCounts
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
}: WatchlistFilterBarProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <Select
        value={signalFilter}
        onValueChange={(value) => onSignalChange(value as SignalFilter)}
      >
        <SelectTrigger className="w-[160px]">
          <SelectValue placeholder="Signal: All" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Signals ({totalCount})</SelectItem>
          <SelectItem value="BUY">🟢 BUY ({counts.signal.BUY || 0})</SelectItem>
          <SelectItem value="HOLD">
            🟡 HOLD ({counts.signal.HOLD || 0})
          </SelectItem>
          <SelectItem value="AVOID">
            🔴 AVOID ({counts.signal.AVOID || 0})
          </SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={styleFilter}
        onValueChange={(value) => onStyleChange(value as StyleFilter)}
      >
        <SelectTrigger className="w-[160px]">
          <SelectValue placeholder="Style: All" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Styles ({totalCount})</SelectItem>
          <SelectItem value="Index">
            📈 Index ({counts.style.Index || 0})
          </SelectItem>
          <SelectItem value="Trend">
            🔥 Trend ({counts.style.Trend || 0})
          </SelectItem>
          <SelectItem value="Value">
            💎 Value ({counts.style.Value || 0})
          </SelectItem>
          <SelectItem value="Swing">
            ⚡ Swing ({counts.style.Swing || 0})
          </SelectItem>
          <SelectItem value="Event">
            📅 Event ({counts.style.Event || 0})
          </SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={riskFilter}
        onValueChange={(value) => onRiskChange(value as RiskFilter)}
      >
        <SelectTrigger className="w-[160px]">
          <SelectValue placeholder="Risk: All" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Risk Levels ({totalCount})</SelectItem>
          <SelectItem value="Low">✓ Low ({counts.risk.Low || 0})</SelectItem>
          <SelectItem value="Medium-Low">
            ⚠ Med-Low ({counts.risk['Medium-Low'] || 0})
          </SelectItem>
          <SelectItem value="Medium">
            ⚠ Medium ({counts.risk.Medium || 0})
          </SelectItem>
          <SelectItem value="High">
            ⚠⚠ High ({counts.risk.High || 0})
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}
