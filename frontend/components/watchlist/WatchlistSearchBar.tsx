import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'

interface WatchlistSearchBarProps {
  value: string
  onChange: (value: string) => void
}

export function WatchlistSearchBar({ value, onChange }: WatchlistSearchBarProps) {
  return (
    <div className="mb-6">
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <Input
          type="text"
          placeholder="Search by symbol or note..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="pl-9"
        />
        {value && (
          <button
            onClick={() => onChange('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            aria-label="Clear search"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  )
}
