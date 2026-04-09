'use client'

import { HomeActionQueue } from '@/components/home/HomeActionQueue'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'

export default function Dashboard() {
  return (
    <PageContainer className="space-y-6 py-8">
      <PageHeader title="Today" />
      <HomeActionQueue />
    </PageContainer>
  )
}
