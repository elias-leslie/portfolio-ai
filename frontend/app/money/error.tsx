'use client'

import { RouteErrorState } from '@/components/shared/RouteErrorState'

export default function MoneyError({
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
      logLabel="Money page error:"
      title="Failed to load money workspace"
      description="Could not load your household finance data. Try refreshing, or return to the dashboard."
    />
  )
}
