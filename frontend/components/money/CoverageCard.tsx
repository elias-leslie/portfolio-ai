import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type { HouseholdCoverage } from '@/lib/api/household'
import { cn } from '@/lib/utils'

/**
 * How much of the household's money the system can actually see.
 *
 * The old score read 99 / "Strong household visibility" beside a stale net
 * worth, because it counted answered setup questions rather than observed
 * facts. Each component is shown with its own evidence so the number can be
 * checked instead of trusted.
 */
export function CoverageCard({ coverage }: { coverage: HouseholdCoverage }) {
  return (
    <SectionCard
      variant="surface"
      title="What we can see"
      description="Coverage of the accounts and spending behind every number here."
    >
      <div className="space-y-3">
        <div className="flex items-baseline gap-3">
          <p className="text-2xl font-semibold text-text">{coverage.score}%</p>
          <Badge
            variant={
              coverage.score >= 85
                ? 'default'
                : coverage.score >= 60
                  ? 'warning'
                  : 'outline'
            }
          >
            {coverage.label}
          </Badge>
        </div>
        <p className="text-sm text-text-muted">{coverage.summary}</p>

        <ul className="space-y-2">
          {coverage.components.map((component) => (
            <li
              key={component.key}
              className="rounded-xl border border-border/30 bg-surface-muted/15 p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-text">
                  {component.label}
                </p>
                <p
                  className={cn(
                    'text-sm',
                    component.score === 100
                      ? 'text-text-muted'
                      : 'text-warning',
                  )}
                >
                  {component.score}%
                </p>
              </div>
              <p className="mt-1 text-xs text-text-muted">{component.detail}</p>
            </li>
          ))}
        </ul>
      </div>
    </SectionCard>
  )
}
