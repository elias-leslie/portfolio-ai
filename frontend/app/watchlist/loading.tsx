import { PageContainer } from '@/components/shared/PageContainer'

export default function WatchlistLoading() {
  return (
    <PageContainer className="space-y-6 py-10">
      <div className="space-y-8">
        {/* Page header skeleton */}
        <div className="flex items-end justify-between">
          <div className="space-y-3">
            <div className="h-10 w-44 animate-pulse rounded-lg bg-surface-muted/60" />
            <div className="h-5 w-72 animate-pulse rounded-md bg-surface-muted/40" />
          </div>
          <div className="h-9 w-32 animate-pulse rounded-lg bg-surface-muted/50" />
        </div>

        {/* Filter bar skeleton */}
        <div className="flex gap-3">
          <div className="h-9 w-64 animate-pulse rounded-lg bg-surface-muted/50" />
          <div className="h-9 w-24 animate-pulse rounded-lg bg-surface-muted/40" />
          <div className="h-9 w-24 animate-pulse rounded-lg bg-surface-muted/40" />
        </div>

        {/* Table skeleton */}
        <div className="rounded-2xl border border-border/40 bg-surface/60">
          {/* Table header */}
          <div className="flex gap-4 border-b border-border/30 px-4 py-3">
            {[80, 48, 64, 48, 48, 64].map((w, i) => (
              <div
                key={`header-skeleton-${i}`}
                className="h-4 animate-pulse rounded bg-surface-muted/50"
                style={{ width: `${w}px` }}
              />
            ))}
          </div>
          {/* Table rows */}
          {[0, 1, 2, 3, 4].map((row) => (
            <div
              key={`row-skeleton-${row}`}
              className="flex items-center gap-4 border-b border-border/20 px-4 py-4 last:border-0"
            >
              <div className="h-5 w-16 animate-pulse rounded bg-surface-muted/60" />
              <div className="h-4 w-32 animate-pulse rounded bg-surface-muted/40" />
              <div className="h-5 w-20 animate-pulse rounded bg-surface-muted/50" />
              <div className="h-4 w-16 animate-pulse rounded bg-surface-muted/40" />
              <div className="h-6 w-14 animate-pulse rounded-full bg-surface-muted/50" />
              <div className="ml-auto h-4 w-20 animate-pulse rounded bg-surface-muted/40" />
            </div>
          ))}
        </div>
      </div>
    </PageContainer>
  )
}
