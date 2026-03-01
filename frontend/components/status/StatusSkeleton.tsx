import { SectionCard } from '@/components/shared/SectionCard'

export function StatusSkeleton() {
  return (
    <SectionCard
      variant="surface"
      title="Loading status"
      description="Fetching telemetry..."
    >
      <div className="space-y-4">
        <div className="h-10 w-48 rounded-lg bg-surface-muted/50 animate-pulse" />
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={`status-skeleton-${index}`}
              className="h-24 rounded-xl bg-surface-muted/40 animate-pulse"
            />
          ))}
        </div>
      </div>
    </SectionCard>
  )
}
