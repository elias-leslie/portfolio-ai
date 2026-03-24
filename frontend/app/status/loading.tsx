import { PageContainer } from '@/components/shared/PageContainer'

export default function StatusLoading() {
  return (
    <PageContainer className="space-y-10 py-10">
      <div className="space-y-8">
        {/* Page header skeleton */}
        <div className="space-y-3">
          <div className="h-3 w-20 animate-pulse rounded bg-surface-muted/40" />
          <div className="h-10 w-52 animate-pulse rounded-lg bg-surface-muted/60" />
          <div className="h-5 w-80 animate-pulse rounded-md bg-surface-muted/40" />
        </div>

        {/* Status cards grid skeleton */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div
              key={`status-skeleton-${i}`}
              className="space-y-3 rounded-2xl border border-border/40 bg-surface/60 p-5"
            >
              <div className="flex items-center justify-between">
                <div className="h-4 w-28 animate-pulse rounded bg-surface-muted/60" />
                <div className="h-6 w-16 animate-pulse rounded-full bg-surface-muted/50" />
              </div>
              <div className="space-y-2">
                <div className="h-3 w-full animate-pulse rounded bg-surface-muted/40" />
                <div className="h-3 w-2/3 animate-pulse rounded bg-surface-muted/30" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </PageContainer>
  )
}
