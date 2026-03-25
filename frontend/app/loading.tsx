import { PageContainer } from '@/components/shared/PageContainer'

export default function HomeLoading() {
  return (
    <PageContainer className="space-y-10 py-10">
      <div className="space-y-8">
        {/* Page header skeleton */}
        <div className="space-y-3">
          <div className="h-10 w-64 skeleton" />
          <div className="h-5 w-96 skeleton" />
        </div>

        {/* Workspace tabs skeleton */}
        <div className="flex gap-2">
          {[0, 1, 2].map((i) => (
            <div
              key={`tab-skeleton-${i}`}
              className="h-9 w-28 skeleton rounded-lg"
            />
          ))}
        </div>

        {/* Content cards skeleton */}
        <div className="grid gap-6 lg:grid-cols-2 animate-stagger">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={`card-skeleton-${i}`}
              className="space-y-4 rounded-2xl border border-border/40 bg-surface/50 p-6"
            >
              <div className="h-5 w-40 skeleton" />
              <div className="space-y-2">
                <div className="h-4 w-full skeleton" />
                <div className="h-4 w-3/4 skeleton" />
                <div className="h-4 w-1/2 skeleton" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </PageContainer>
  )
}
