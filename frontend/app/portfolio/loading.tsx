import { PageContainer } from '@/components/shared/PageContainer'

export default function PortfolioLoading() {
  return (
    <PageContainer className="space-y-10 py-10">
      <div className="space-y-8">
        {/* Page header skeleton */}
        <div className="space-y-3">
          <div className="skeleton rounded-lg h-10 w-48" />
          <div className="skeleton rounded-md h-5 w-80" />
        </div>

        {/* Stats row skeleton */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={`stat-skeleton-${i}`}
              className="space-y-2 rounded-2xl border border-border/40 bg-surface/60 p-4"
            >
              <div className="skeleton h-3 w-20" />
              <div className="skeleton h-7 w-28" />
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
                  <div className="skeleton h-5 w-48" />
                  <div className="skeleton h-4 w-32" />
                </div>
                <div className="skeleton rounded-full h-10 w-10" />
              </div>
              <div className="mt-4 space-y-2">
                {[0, 1, 2].map((row) => (
                  <div
                    key={`position-skeleton-${i}-${row}`}
                    className="skeleton rounded-lg h-10 w-full"
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
