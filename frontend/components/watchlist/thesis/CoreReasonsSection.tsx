import type { CoreReason } from '@/lib/api/thesis'

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'bg-status-success'
  if (confidence >= 0.6) return 'bg-status-info'
  if (confidence >= 0.4) return 'bg-status-warning'
  return 'bg-status-error'
}

export function CoreReasonsSection({ reasons }: { reasons: CoreReason[] }) {
  if (reasons.length === 0) return null

  return (
    <div className="space-y-2">
      <h5 className="text-xs font-semibold text-text">Core Reasons</h5>
      <div className="space-y-2">
        {reasons.map((reason, idx) => (
          <div key={idx} className="space-y-1">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm text-text flex-1">{reason.reason}</p>
              <span className="text-xs font-semibold text-text-muted min-w-[40px] text-right">
                {(reason.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
              <div
                className={`h-full ${getConfidenceColor(reason.confidence)} transition-all`}
                style={{ width: `${reason.confidence * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
