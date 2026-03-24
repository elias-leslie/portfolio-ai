import { PageContainer } from '@/components/shared/PageContainer'

export default function SymbolLoading() {
  return (
    <PageContainer className="space-y-10 py-10">
      <div className="space-y-8">
        {/* Symbol header skeleton */}
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-24 animate-pulse rounded-lg bg-surface-muted/60" />
            <div className="h-7 w-16 animate-pulse rounded-full bg-surface-muted/50" />
          </div>
          <div className="h-5 w-64 animate-pulse rounded-md bg-surface-muted/40" />
        </div>

        {/* Score cards skeleton */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={`score-skeleton-${i}`}
              className="space-y-2 rounded-2xl border border-border/40 bg-surface/60 p-4"
            >
              <div className="h-3 w-16 animate-pulse rounded bg-surface-muted/50" />
              <div className="h-8 w-12 animate-pulse rounded bg-surface-muted/70" />
            </div>
          ))}
        </div>

        {/* Workspace tabs skeleton */}
        <div className="flex gap-2">
          {[0, 1, 2].map((i) => (
            <div
              key={`tab-skeleton-${i}`}
              className="h-9 w-28 animate-pulse rounded-lg bg-surface-muted/50"
            />
          ))}
        </div>

        {/* Content skeleton */}
        <div className="space-y-4 rounded-2xl border border-border/40 bg-surface/60 p-6">
          <div className="h-5 w-48 animate-pulse rounded bg-surface-muted/60" />
          <div className="space-y-2">
            <div className="h-4 w-full animate-pulse rounded bg-surface-muted/40" />
            <div className="h-4 w-5/6 animate-pulse rounded bg-surface-muted/35" />
            <div className="h-4 w-2/3 animate-pulse rounded bg-surface-muted/30" />
          </div>
        </div>
      </div>
    </PageContainer>
  )
}
