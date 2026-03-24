import { PageContainer } from '@/components/shared/PageContainer'

export default function PortfolioLoading() {
  return (
    <PageContainer className="space-y-10 py-10">
      <div className="space-y-8">
        {/* Page header skeleton */}
        <div className="space-y-3">
          <div className="h-10 w-48 animate-pulse rounded-lg bg-surface-muted/60" />
          <div className="h-5 w-80 animate-pulse rounded-md bg-surface-muted/40" />
        </div>

        {/* Stats row skeleton */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={`stat-skeleton-${i}`}
              className="space-y-2 rounded-2xl border border-border/40 bg-surface/60 p-4"
            >
              <div className="h-3 w-20 animate-pulse rounded bg-surface-muted/50" />
              <div className="h-7 w-28 animate-pulse rounded bg-surface-muted/70" />
            </div>
          ))}
        </div>

        {/* Accounts skeleton */}
        <div className="space-y-4">
          {[0, 1].map((i) => (
            <div
              key={`account-skeleton-${i}`}
              className="rounded-2xl border border-border/40 bg-surface/60 p-6"
            >
              <div className="flex items-center justify-between">
                <div className="space-y-2">
                  <div className="h-5 w-48 animate-pulse rounded bg-surface-muted/70" />
                  <div className="h-4 w-32 animate-pulse rounded bg-surface-muted/50" />
                </div>
                <div className="h-10 w-10 animate-pulse rounded-full bg-surface-muted/60" />
              </div>
              <div className="mt-4 space-y-2">
                {[0, 1, 2].map((row) => (
                  <div
                    key={`position-skeleton-${i}-${row}`}
                    className="h-10 w-full animate-pulse rounded-lg bg-surface-muted/40"
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </PageContainer>
  )
}
