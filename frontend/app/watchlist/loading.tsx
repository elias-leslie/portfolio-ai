import { PageContainer } from '@/components/shared/PageContainer'

export default function WatchlistLoading() {
  return (
    <PageContainer className="space-y-6 py-10">
      <div className="space-y-8">
        {/* Page header skeleton */}
        <div className="flex items-end justify-between">
          <div className="space-y-3">
            <div className="skeleton rounded-lg h-10 w-44" />
            <div className="skeleton rounded-md h-5 w-72" />
          </div>
          <div className="skeleton rounded-lg h-9 w-32" />
        </div>

        {/* Filter bar skeleton */}
        <div className="flex gap-3">
          <div className="skeleton rounded-lg h-9 w-64" />
          <div className="skeleton rounded-lg h-9 w-24" />
          <div className="skeleton rounded-lg h-9 w-24" />
        </div>

        {/* Table skeleton */}
        <div className="rounded-2xl border border-border/40 bg-surface/60">
          {/* Table header */}
          <div className="flex gap-4 border-b border-border/30 px-4 py-3">
            {[80, 48, 64, 48, 48, 64].map((w, i) => (
              <div
                key={`header-skeleton-${i}`}
                className="skeleton h-4"
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
              <div className="skeleton h-5 w-16" />
              <div className="skeleton h-4 w-32" />
              <div className="skeleton h-5 w-20" />
              <div className="skeleton h-4 w-16" />
              <div className="skeleton rounded-full h-6 w-14" />
              <div className="skeleton ml-auto h-4 w-20" />
            </div>
          ))}
        </div>
      </div>
    </PageContainer>
  )
}
