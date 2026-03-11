import type { ReactNode } from 'react'
import { useId } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface LoadErrorStateProps {
  title: string
  detail?: string
  onRetry?: () => void
  isRetrying?: boolean
  retryLabel?: string
  className?: string
  secondaryAction?: ReactNode
}

export function LoadErrorState({
  title,
  detail,
  onRetry,
  isRetrying = false,
  retryLabel = 'Retry',
  className,
  secondaryAction,
}: LoadErrorStateProps) {
  const detailId = useId()

  return (
    <div
      role="alert"
      aria-live="polite"
      aria-describedby={detail ? detailId : undefined}
      className={cn(
        'rounded-2xl border border-loss/30 bg-loss/10 p-5 text-sm text-loss',
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="space-y-2">
          <p className="font-medium">{title}</p>
          {detail ? (
            <p id={detailId} className="text-loss/80">
              {detail}
            </p>
          ) : null}
          {onRetry || secondaryAction ? (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {onRetry ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={onRetry}
                  disabled={isRetrying}
                >
                  <RefreshCw
                    className={cn('mr-2 h-4 w-4', isRetrying && 'animate-spin')}
                  />
                  {retryLabel}
                </Button>
              ) : null}
              {secondaryAction}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
