'use client'

import { RouteErrorState } from '@/components/shared/RouteErrorState'

export default function WatchlistError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <RouteErrorState
      error={error}
      reset={reset}
      logLabel="Watchlist page error:"
      title="Failed to load watchlist"
      description="Could not load your watchlist data. The market data service may be temporarily unavailable."
    />
  )
}
