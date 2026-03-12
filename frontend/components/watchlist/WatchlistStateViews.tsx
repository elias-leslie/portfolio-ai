import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { Button } from '@/components/ui/button'

interface WatchlistErrorViewProps {
  message: string
  onRetry: () => void
  isRetrying?: boolean
}

interface WatchlistEmptyStateProps {
  title: string
  detail: string
  primaryAction?: {
    label: string
    onClick: () => void
  }
}

export function WatchlistErrorView({
  message,
  onRetry,
  isRetrying = false,
}: WatchlistErrorViewProps) {
  return (
    <LoadErrorState
      title="Failed to load the watchlist."
      detail={message}
      onRetry={onRetry}
      isRetrying={isRetrying}
      retryLabel="Retry watchlist"
      className="mb-6"
    />
  )
}

export function WatchlistLoadingSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-live="polite">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-16 animate-pulse rounded-md bg-surface-muted" />
      ))}
    </div>
  )
}

export function WatchlistEmptyState({
  title,
  detail,
  primaryAction,
}: WatchlistEmptyStateProps) {
  return (
    <div className="rounded-md border border-border bg-surface p-8 text-center">
      <p className="text-sm font-medium text-text">{title}</p>
      <p className="mt-2 text-sm text-text-muted">{detail}</p>
      {primaryAction ? (
        <div className="mt-4">
          <Button type="button" variant="outline" onClick={primaryAction.onClick}>
            {primaryAction.label}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
