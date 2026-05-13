'use client'

export const dynamic = 'force-dynamic'

import { TodayOverviewPanel } from '@/components/home/TodayOverviewPanel'
import { InvestingMarketTrendPanels } from '@/components/portfolio/InvestingMarketPanel'
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
      <TodayOverviewPanel />
      <InvestingMarketTrendPanels />
    </PageContainer>
  )
}
