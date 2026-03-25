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
    <div className="overflow-hidden rounded-xl border border-border/40 bg-surface/60" role="status" aria-live="polite">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-center gap-4 border-b border-border/30 px-4 py-3 last:border-b-0">
          <div className="h-4 w-16 skeleton" />
          <div className="h-4 w-20 skeleton" />
          <div className="h-5 w-10 skeleton rounded-md" />
          <div className="flex-1" />
          <div className="h-4 w-20 skeleton" />
        </div>
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
    <div className="rounded-2xl border border-dashed border-border/40 bg-gradient-to-br from-surface-muted/10 to-surface/30 px-6 py-14 text-center">
      <div className="relative mx-auto mb-6">
        <div className="absolute inset-0 mx-auto h-14 w-14 rounded-full bg-primary/10 blur-xl" />
        <div className="relative mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-primary/20 bg-primary/10">
          <Eye className="h-7 w-7 text-primary" />
        </div>
      </div>
      <p className="font-display italic text-xl text-text">{title}</p>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-text-muted">{detail}</p>
      {primaryAction ? (
        <div className="mt-6">
          <Button type="button" onClick={primaryAction.onClick}>
            {primaryAction.label}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
