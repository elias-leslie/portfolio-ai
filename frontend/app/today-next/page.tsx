'use client'

export const dynamic = 'force-dynamic'

import Link from 'next/link'
import { TodayOverviewPanel } from '@/components/home/TodayOverviewPanel'
import { InvestingMarketTrendPanels } from '@/components/portfolio/InvestingMarketPanel'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { DeploymentZoneHero } from '@/components/signals/DeploymentZoneHero'
import { TodaySignalsDigest } from '@/components/signals/TodaySignalsDigest'
import { Button } from '@/components/ui/button'

export default function TodayNextPage() {
  return (
    <PageContainer className="space-y-4 py-5">
      <PageHeader
        title="Today-next"
        description="Three-tier signal stack: macro deployment gate, quant scanner, and AI committee — alongside today's household snapshot."
        eyebrow="Signals Preview"
        size="md"
        variant="plain"
        actions={
          <Button asChild variant="outline">
            <Link href="/">Back to Today</Link>
          </Button>
        }
      />
      <DeploymentZoneHero />
      <TodayOverviewPanel />
      <TodaySignalsDigest />
      <InvestingMarketTrendPanels />
    </PageContainer>
  )
}
