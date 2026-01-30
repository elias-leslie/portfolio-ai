'use client'

import { CheckCircle2, Database, Trash2 } from 'lucide-react'
import type { LastRunSummary } from '@/lib/api/maintenance'
import { MaintenanceItem, SectionHeader } from '../MaintenanceComponents'

interface DatabaseMaintenanceSectionProps {
  lastRunSummary: LastRunSummary | null
  triggeringTask: string | null
  liveBlocked: boolean
  onCleanupNews: () => void
  onVacuumDatabase: () => void
  onValidateIntegrity: () => void
}

export function DatabaseMaintenanceSection({
  lastRunSummary,
  triggeringTask,
  liveBlocked,
  onCleanupNews,
  onVacuumDatabase,
  onValidateIntegrity,
}: DatabaseMaintenanceSectionProps) {
  const cleanupNews =
    lastRunSummary?.tasks?.cleanupOldNewsTask ||
    lastRunSummary?.tasks?.cleanupNews

  const vacuumDb =
    lastRunSummary?.tasks?.vacuumDatabaseTask ||
    lastRunSummary?.tasks?.vacuumDatabase

  const validateIntegrity =
    lastRunSummary?.tasks?.validateIntegrityTask ||
    lastRunSummary?.tasks?.validateIntegrity

  return (
    <>
      <SectionHeader
        title="Database Maintenance"
        icon={<Database className="h-4 w-4 text-muted-foreground" />}
      />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MaintenanceItem
          title="Cleanup News"
          icon={<Trash2 className="h-5 w-5 text-status-warning" />}
          metrics={[
            {
              label: 'Deleted',
              value: String(
                (cleanupNews?.summary as Record<string, unknown>)?.deleted ||
                  '—',
              ),
            },
          ]}
          badge={{ text: '90 days retention' }}
          lastRun={cleanupNews || null}
          onTrigger={onCleanupNews}
          isTriggering={triggeringTask === 'cleanup_news'}
          disabled={liveBlocked}
        />
        <MaintenanceItem
          title="Vacuum Database"
          icon={<Database className="h-5 w-5 text-status-info" />}
          metrics={[
            {
              label: 'Reclaimed',
              value: `${(vacuumDb?.summary as Record<string, unknown>)?.totalReclaimedMb || '—'} MB`,
            },
          ]}
          badge={{ text: 'Weekly' }}
          lastRun={vacuumDb || null}
          onTrigger={onVacuumDatabase}
          isTriggering={triggeringTask === 'vacuum_database'}
          disabled={liveBlocked}
        />
        <MaintenanceItem
          title="Validate Integrity"
          icon={<CheckCircle2 className="h-5 w-5 text-status-success" />}
          metrics={[
            {
              label: 'Errors',
              value: String(
                (validateIntegrity?.summary as Record<string, unknown>)
                  ?.totalErrors || '—',
              ),
            },
            {
              label: 'Warnings',
              value: String(
                (validateIntegrity?.summary as Record<string, unknown>)
                  ?.totalWarnings || '—',
              ),
            },
          ]}
          badge={{ text: 'Daily' }}
          lastRun={validateIntegrity || null}
          onTrigger={onValidateIntegrity}
          isTriggering={triggeringTask === 'validate_integrity'}
          disabled={liveBlocked}
        />
      </div>
    </>
  )
}
