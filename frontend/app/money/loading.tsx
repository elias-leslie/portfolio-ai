import { PageContainer } from '@/components/shared/PageContainer'

export default function MoneyLoading() {
  return (
    <PageContainer className="space-y-10 py-10">
      <div className="space-y-8">
        {/* Page header skeleton */}
        <div className="space-y-3">
          <div className="skeleton rounded-lg h-10 w-56" />
          <div className="skeleton rounded-md h-5 w-96" />
        </div>

        {/* Workspace tabs skeleton */}
        <div className="flex gap-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={`tab-skeleton-${i}`}
              className="skeleton rounded-lg h-9 w-32"
            />
          ))}
        </div>

        {/* Content grid skeleton */}
        <div className="grid gap-6 lg:grid-cols-2">
          {[0, 1].map((i) => (
            <div
              key={`panel-skeleton-${i}`}
              className="space-y-4 rounded-2xl border border-border/40 bg-surface/60 p-6"
            >
              <div className="skeleton h-5 w-44" />
              <div className="space-y-3">
                {[0, 1, 2].map((row) => (
                  <div
                    key={`row-skeleton-${i}-${row}`}
                    className="skeleton rounded-xl h-12 w-full"
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
