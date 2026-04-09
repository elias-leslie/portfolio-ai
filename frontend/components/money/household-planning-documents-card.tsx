import { Badge } from '@/components/ui/badge'
import type { HouseholdDocumentRequirement } from '@/lib/api/household-planning'
import { formatEnumLabel } from '@/lib/formatters'

export function HouseholdPlanningDocumentsCard({
  requirements,
  statusBadge,
}: {
  requirements: HouseholdDocumentRequirement[]
  statusBadge: (status: string) => 'outline' | 'secondary' | 'success'
}) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text">
            Evidence gaps Jenny sees
          </p>
          <p className="mt-1 text-sm text-text-muted">
            Durable evidence Jenny still wants before she treats related
            planning assumptions as grounded.
          </p>
        </div>
        <Badge variant="outline">{requirements.length}</Badge>
      </div>
      <div className="mt-4 space-y-3">
        {requirements.length === 0 ? (
          <p className="text-sm text-text-muted">
            No evidence gaps surfaced yet.
          </p>
        ) : (
          requirements.map((requirement) => (
            <div
              key={requirement.id}
              className="rounded-xl border border-border/40 bg-surface/70 p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-text">
                  {requirement.label}
                </p>
                <Badge variant={statusBadge(requirement.status)}>
                  {formatEnumLabel(requirement.status)}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-text-muted">
                {requirement.rationale ??
                  'Jenny needs stronger evidence here before she can trust the planning assumption.'}
              </p>
              <p className="mt-2 text-xs uppercase tracking-wide text-text-muted">
                {formatEnumLabel(requirement.priority)} priority
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
