import type { KeyCatalyst } from '@/lib/api/thesis'
import { formatTimestamp } from '../ExpandedRowUtils'
import { ImpactBadge } from './ImpactBadge'

export function KeyCatalystsSection({
  catalysts,
  userTimezone,
}: {
  catalysts: KeyCatalyst[]
  userTimezone: string
}) {
  return (
    <div className="border-t border-border pt-3 space-y-2">
      <h5 className="text-xs font-semibold text-text">Key Catalysts</h5>
      <div className="space-y-2">
        {catalysts.map((catalyst) => (
          <div key={catalyst.catalyst} className="flex items-start gap-2">
            <ImpactBadge impact={catalyst.impact} />
            <div className="flex-1">
              <p className="text-sm text-text">{catalyst.catalyst}</p>
              {catalyst.expectedDate && (
                <p className="text-xs text-text-muted mt-0.5">
                  Expected:{' '}
                  {formatTimestamp(catalyst.expectedDate, userTimezone)}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
