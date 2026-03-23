import { Search, X } from 'lucide-react'
import { Input } from '@/components/ui/input'

interface WatchlistSearchBarProps {
  value: string
  onChange: (value: string) => void
  resultCount: number
  totalCount: number
}

export function WatchlistSearchBar({
  value,
  onChange,
  resultCount,
  totalCount,
}: WatchlistSearchBarProps) {
  const helperText =
    value.trim().length > 0
      ? `${resultCount} of ${totalCount} ${totalCount === 1 ? 'symbol' : 'symbols'} shown`
      : 'Search symbol, note, thesis headline, or signal'

  return (
    <div>
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <Input
          type="text"
          placeholder="Search symbol, note, thesis, or signal..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="pl-9"
          aria-describedby="watchlist-search-helper"
        />
        {value && (
          <button
            type="button"
            onClick={() => onChange('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer rounded-full p-1 text-text-muted transition-colors duration-150 hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            aria-label="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <p id="watchlist-search-helper" className="mt-2 text-xs text-text-muted">
        {helperText}
      </p>
    </div>
  )
}
