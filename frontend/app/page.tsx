'use client'

export const dynamic = 'force-dynamic'

import { HomeActionQueue } from '@/components/home/HomeActionQueue'
import { TodayOverviewPanel } from '@/components/home/TodayOverviewPanel'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { useClientReady } from '@/lib/hooks/useClientReady'

function DashboardContent() {
  return (
    <PageContainer className="space-y-6 py-8">
      <PageHeader title="Today" />
      <TodayOverviewPanel />
      <HomeActionQueue />
    </PageContainer>
  )
}

export default function Dashboard() {
  const ready = useClientReady()

  if (!ready) {
    return (
      <PageContainer className="space-y-6 py-8">
        <PageHeader title="Today" />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4" role="status">
          {[...Array(8)].map((_, index) => (
            <div
              key={`today-overview-skeleton-${index}`}
              className="h-28 rounded-2xl skeleton"
            />
          ))}
        </div>
        <div className="grid gap-3 lg:grid-cols-2" role="status">
          {[...Array(4)].map((_, index) => (
            <div
              key={`today-action-skeleton-${index}`}
              className="h-28 rounded-2xl skeleton"
            />
          ))}
        </div>
      </PageContainer>
    )
  }

  return <DashboardContent />
}
