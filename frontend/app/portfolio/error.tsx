'use client'

import { RouteErrorState } from '@/components/shared/RouteErrorState'

export default function PortfolioError({
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
      logLabel="Portfolio page error:"
      title="Failed to load portfolio"
      description="Could not load your portfolio data. Try refreshing, or return to the dashboard."
    />
  )
}
