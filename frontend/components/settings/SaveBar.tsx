'use client'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface SaveBarProps {
  hasChanges: boolean
  onSave: () => void
  onReset: () => void
  isPending?: boolean
  className?: string
  changeCount?: number
}

export function SaveBar({
  hasChanges,
  onSave,
  onReset,
  isPending = false,
  className,
  changeCount,
}: SaveBarProps) {
  if (!hasChanges) return null

  return (
    <div
      className={cn(
        'sticky bottom-0 z-10 flex items-center justify-between border-t border-border bg-surface-elev/95 px-4 py-3 backdrop-blur-sm sm:px-6 lg:px-8',
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/20 text-xs font-semibold text-primary">
          {changeCount || '•'}
        </div>
        <p className="text-sm text-text-muted">
          {changeCount ? (
            <>
              <span className="font-medium text-text">{changeCount}</span>{' '}
              unsaved change{changeCount > 1 ? 's' : ''}
            </>
          ) : (
            'You have unsaved changes'
          )}
        </p>
      </div>

      <div className="flex gap-3">
        <Button
          variant="outline"
          onClick={onReset}
          disabled={isPending}
          size="sm"
        >
          Reset
        </Button>
        <Button onClick={onSave} disabled={isPending} size="sm">
          {isPending ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  )
}
