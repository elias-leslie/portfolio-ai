'use client'

export const dynamic = 'force-dynamic'

import { DailyBriefPanel } from '@/components/home/DailyBriefPanel'
import { HomeNextActions } from '@/components/home/HomeNextActions'
import { InvestingMarketTrendPanels } from '@/components/portfolio/InvestingMarketPanel'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'

export default function Dashboard() {
  return (
    <PageContainer className="space-y-6 py-5">
      <PageHeader
        title="Today"
        eyebrow="Daily Briefing"
        size="md"
        variant="plain"
      />
      <HomeNextActions />
      <DailyBriefPanel />
      <InvestingMarketTrendPanels />
    </PageContainer>
  )
}
