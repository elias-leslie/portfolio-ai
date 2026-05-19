'use client'

export const dynamic = 'force-dynamic'

import { TodayOverviewPanel } from '@/components/home/TodayOverviewPanel'
import { InvestingMarketTrendPanels } from '@/components/portfolio/InvestingMarketPanel'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { DeploymentZoneHero } from '@/components/signals/DeploymentZoneHero'
import { TodaySignalsDigest } from '@/components/signals/TodaySignalsDigest'

export default function Dashboard() {
  return (
    <PageContainer className="space-y-6 py-5">
      <PageHeader
        title="Today"
        description="Macro gate, household snapshot, today's signal lanes, and market tape — one screen, ready to act."
        eyebrow="Daily Briefing"
        size="md"
        variant="plain"
      />
      <DeploymentZoneHero />
      <TodayOverviewPanel />
      <TodaySignalsDigest />
      <InvestingMarketTrendPanels />
    </PageContainer>
  )
}
