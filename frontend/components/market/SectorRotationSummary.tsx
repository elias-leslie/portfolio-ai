/**
 * SectorRotationSummary Component
 *
 * Displays sector performance grouped into Leading/Neutral/Lagging.
 * Shows plain-language sector names with descriptions.
 */

'use client'

import { InfoTooltip } from '@/components/ui/info-tooltip'
import type {
  SectorInfo,
  SectorRotationSummary as SectorRotation,
} from '@/lib/api/market'
import { cn } from '@/lib/utils'

export interface SectorRotationSummaryProps {
  /**
   * Sector rotation data
   */
  rotation: SectorRotation

  /**
   * Additional CSS classes
   */
  className?: string
}

function SectorBadge({ sector }: { sector: SectorInfo }) {
  const signalColor =
    sector.signal === 'Leading'
      ? 'text-gain'
      : sector.signal === 'Lagging'
        ? 'text-loss'
        : 'text-warning'

  return (
    <div className="flex items-center justify-between gap-2">
      <div className="flex items-center gap-1.5">
        <span className="text-sm font-medium text-text">{sector.name}</span>
        <InfoTooltip content={sector.description} side="top" iconSize={11} />
      </div>
      <div className="flex items-center gap-2">
        {sector.changePct !== null && (
          <span className={cn('text-xs font-semibold', signalColor)}>
            {sector.changePct > 0 ? '+' : ''}
            {sector.changePct.toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  )
}

export function SectorRotationSummary({
  rotation,
  className,
}: SectorRotationSummaryProps) {
  return (
    <div className={cn('space-y-4', className)}>
      {/* Leading Sectors */}
      {rotation.leading.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-2xl" role="img" aria-label="Leading">
              🟢
            </span>
            <h4 className="text-sm font-semibold text-text">
              Leading ({rotation.leadingCount})
            </h4>
          </div>
          <div className="space-y-2 pl-8">
            {rotation.leading.map((sector) => (
              <SectorBadge key={sector.symbol} sector={sector} />
            ))}
          </div>
        </div>
      )}

      {/* Neutral Sectors */}
      {rotation.neutral.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-2xl" role="img" aria-label="Neutral">
              🟡
            </span>
            <h4 className="text-sm font-semibold text-text">
              Neutral ({rotation.neutralCount})
            </h4>
          </div>
          <div className="space-y-2 pl-8">
            {rotation.neutral.map((sector) => (
              <SectorBadge key={sector.symbol} sector={sector} />
            ))}
          </div>
        </div>
      )}

      {/* Lagging Sectors */}
      {rotation.lagging.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-2xl" role="img" aria-label="Lagging">
              🔴
            </span>
            <h4 className="text-sm font-semibold text-text">
              Lagging ({rotation.laggingCount})
            </h4>
          </div>
          <div className="space-y-2 pl-8">
            {rotation.lagging.map((sector) => (
              <SectorBadge key={sector.symbol} sector={sector} />
            ))}
          </div>
        </div>
      )}

      {/* Footer explanation */}
      <div className="pt-3 border-t border-border">
        <p className="text-xs text-text-muted">
          Sectors ranked by today&apos;s performance. Leading = top 33%, Lagging
          = bottom 33%.
        </p>
      </div>
    </div>
  )
}
