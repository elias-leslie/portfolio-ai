'use client'

import { RouteErrorState } from '@/components/shared/RouteErrorState'

export default function StatusError({
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
      logLabel="Status page error:"
      title="Failed to load system status"
      description="Could not load the system health dashboard. The health check service may be temporarily unavailable."
    />
  )
}
