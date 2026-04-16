'use client'

export const dynamic = 'force-dynamic'

import { HomeActionQueue } from '@/components/home/HomeActionQueue'
import { TodayMarketPulsePanel } from '@/components/home/TodayMarketPulsePanel'
import { TodayOverviewPanel } from '@/components/home/TodayOverviewPanel'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'

export default function Dashboard() {
  return (
    <PageContainer className="space-y-4 py-5">
      <PageHeader
        title="Today"
        description="One-screen command board for household position, market tape, and next moves."
        eyebrow="Daily Briefing"
        size="md"
        variant="plain"
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(22rem,0.84fr)_minmax(0,1.16fr)] xl:items-start">
        <div className="space-y-4">
          <TodayOverviewPanel />
          <HomeActionQueue />
        </div>
        <TodayMarketPulsePanel />
      </div>
    </PageContainer>
  )
}
