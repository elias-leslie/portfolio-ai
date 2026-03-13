import { ChevronDown, ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { formatLabel } from './RuleSectionCard'

interface CatalystImpactsCardProps {
  data: Record<string, { impact: number; durationDays: number }>
  isExpanded: boolean
  onToggle: (title: string) => void
}

const SECTION_KEY = 'catalyst_impacts'

export function CatalystImpactsCard({
  data,
  isExpanded,
  onToggle,
}: CatalystImpactsCardProps) {
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <button
        type="button"
        onClick={() => onToggle(SECTION_KEY)}
        aria-expanded={isExpanded}
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} catalyst impacts`}
        className="w-full flex items-center justify-between p-4 hover:bg-surface-hover transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="h-5 w-5 text-text-muted" />
          ) : (
            <ChevronRight className="h-5 w-5 text-text-muted" />
          )}
          <span className="font-semibold text-text">Catalyst Impacts</span>
          <Badge variant="outline" className="text-xs">
            {Object.keys(data).length} events
          </Badge>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-border bg-surface-muted/30 p-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(data)
              .sort((a, b) => b[1].impact - a[1].impact)
              .map(([eventType, catalyst]) => (
                <div
                  key={eventType}
                  className="rounded border border-border bg-surface p-3"
                >
                  <div className="text-sm font-medium text-text mb-2">
                    {formatLabel(eventType)}
                  </div>
                  <div className="flex items-center gap-3">
                    <div>
                      <div className="text-xs text-text-muted">Impact</div>
                      <div
                        className={cn(
                          'text-base font-semibold',
                          catalyst.impact > 0
                            ? 'text-gain'
                            : catalyst.impact < 0
                              ? 'text-loss'
                              : 'text-text-muted',
                        )}
                      >
                        {catalyst.impact > 0 ? '+' : ''}
                        {catalyst.impact.toFixed(1)}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-text-muted">Duration</div>
                      <div className="text-base font-semibold text-text">
                        {catalyst.durationDays}d
                      </div>
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
