'use client'

import type { DataRouting } from '@/lib/api/sources'

interface DataRoutingSectionProps {
  dataRouting: Record<string, DataRouting>
}

export function DataRoutingSection({ dataRouting }: DataRoutingSectionProps) {
  if (Object.keys(dataRouting).length === 0) return null

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h3 className="font-semibold text-foreground mb-3">
        Data Routing Recommendations
      </h3>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(dataRouting).map(([dataType, routing]) => (
          <div
            key={dataType}
            className="rounded border border-border bg-surface-muted/30 p-3"
          >
            <div className="font-medium text-sm text-foreground">{dataType}</div>
            <div className="text-xs text-muted-foreground mt-1">
              Primary:{' '}
              <span className="text-foreground">{routing.primary}</span>
              {routing.fallback1 && <> → {routing.fallback1}</>}
              {routing.fallback2 && <> → {routing.fallback2}</>}
            </div>
            {routing.notes && (
              <div className="text-xs text-muted-foreground mt-1 italic">
                {routing.notes}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
