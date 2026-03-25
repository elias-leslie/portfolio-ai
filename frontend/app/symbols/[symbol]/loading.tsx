import { PageContainer } from '@/components/shared/PageContainer'

export default function SymbolLoading() {
  return (
    <PageContainer className="space-y-10 py-10">
      <div className="space-y-8">
        {/* Symbol header skeleton */}
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="skeleton rounded-lg h-10 w-24" />
            <div className="skeleton rounded-full h-7 w-16" />
          </div>
          <div className="skeleton rounded-md h-5 w-64" />
        </div>

        {/* Score cards skeleton */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={`score-skeleton-${i}`}
              className="space-y-2 rounded-2xl border border-border/40 bg-surface/60 p-4"
            >
              <div className="skeleton h-3 w-16" />
              <div className="skeleton h-8 w-12" />
            </div>
          ))}
        </div>

        {/* Workspace tabs skeleton */}
        <div className="flex gap-2">
          {[0, 1, 2].map((i) => (
            <div
              key={`tab-skeleton-${i}`}
              className="skeleton rounded-lg h-9 w-28"
            />
          ))}
        </div>

        {/* Content skeleton */}
        <div className="space-y-4 rounded-2xl border border-border/40 bg-surface/60 p-6">
          <div className="skeleton h-5 w-48" />
          <div className="space-y-2">
            <div className="skeleton h-4 w-full" />
            <div className="skeleton h-4 w-5/6" />
            <div className="skeleton h-4 w-2/3" />
          </div>
        </div>
      </div>
    </PageContainer>
  )
}
