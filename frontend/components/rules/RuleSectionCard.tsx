import { ChevronDown, ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface RuleSectionCardProps {
  title: string
  data: Record<string, unknown>
  isExpanded: boolean
  onToggle: (title: string) => void
}

export function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function formatValue(value: unknown): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') {
    if (value < 1 && value > -1 && value !== 0) {
      return `${(value * 100).toFixed(2)}%`
    }
    return value.toString()
  }
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

export function RuleSectionCard({
  title,
  data,
  isExpanded,
  onToggle,
}: RuleSectionCardProps) {
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <button
        type="button"
        onClick={() => onToggle(title)}
        aria-expanded={isExpanded}
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${title}`}
        className="w-full flex items-center justify-between p-4 hover:bg-surface-hover transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="h-5 w-5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          )}
          <span className="font-semibold text-foreground">
            {formatLabel(title)}
          </span>
          <Badge variant="outline" className="text-xs">
            {Object.keys(data).length} rules
          </Badge>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-border bg-surface-muted/30 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(data).map(([key, value]) => (
              <div
                key={key}
                className="rounded border border-border bg-surface p-3"
              >
                <div className="text-sm font-medium text-muted-foreground mb-1">
                  {formatLabel(key)}
                </div>
                <div className="text-base font-semibold text-foreground">
                  {formatValue(value)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
