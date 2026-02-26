interface WatchlistErrorViewProps {
  message: string
}

export function WatchlistErrorView({ message }: WatchlistErrorViewProps) {
  return (
    <div className="mb-6 rounded-md border border-loss bg-loss/10 p-4 text-sm text-loss">
      Failed to load watchlist: {message}
    </div>
  )
}

export function WatchlistLoadingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-16 animate-pulse rounded-md bg-surface-muted" />
      ))}
    </div>
  )
}
