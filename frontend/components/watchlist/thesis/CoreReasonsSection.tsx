import type { CoreReason } from '@/lib/api/thesis'
import { cn } from '@/lib/utils'

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'bg-gain'
  if (confidence >= 0.6) return 'bg-accent'
  if (confidence >= 0.4) return 'bg-warning'
  return 'bg-loss'
}

export function CoreReasonsSection({ reasons }: { reasons: CoreReason[] }) {
  if (reasons.length === 0) return null

  return (
    <div className="space-y-2">
      <h5 className="text-xs font-semibold text-text">Core Reasons</h5>
      <div className="space-y-2">
        {reasons.map((reason) => (
          <div key={reason.reason} className="space-y-1">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm text-text flex-1">{reason.reason}</p>
              <span className="text-xs font-semibold text-text-muted min-w-[40px] text-right">
                {(reason.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
              <div
                className={cn('h-full transition-all', getConfidenceColor(reason.confidence))}
                style={{ width: `${reason.confidence * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
