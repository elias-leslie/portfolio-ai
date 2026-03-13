import { Eye } from 'lucide-react'
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
    <div className="space-y-3" role="status" aria-live="polite">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-16 animate-pulse rounded-xl bg-surface-muted/50" />
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
    <div className="rounded-2xl border border-border/50 bg-surface/60 p-10 text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
        <Eye className="h-6 w-6 text-primary" />
      </div>
      <p className="text-sm font-medium text-text">{title}</p>
      <p className="mx-auto mt-2 max-w-sm text-sm text-text-muted leading-relaxed">{detail}</p>
      {primaryAction ? (
        <div className="mt-5">
          <Button type="button" onClick={primaryAction.onClick}>
            {primaryAction.label}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
