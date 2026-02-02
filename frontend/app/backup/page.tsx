'use client'

import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'

import {
  BackupHistoryCard,
  BackupStatusCard,
  RestoreInfoCard,
  TriggerBackupCard,
} from './components'

export default function BackupPage() {
  return (
    <PageContainer className="py-6">
      <PageHeader
        title="Backup Management"
        description="Manage project backups stored on Davion-Sidar"
      />

      <div className="grid gap-6 mt-6 lg:grid-cols-2">
        <BackupStatusCard />
        <TriggerBackupCard />
        <BackupHistoryCard />
        <RestoreInfoCard />
      </div>
    </PageContainer>
  )
}
