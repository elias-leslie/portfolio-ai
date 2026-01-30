'use client'

import { Camera, FileX, ServerCrash, Trash2, Users } from 'lucide-react'
import { MaintenanceItem, SectionHeader } from '../MaintenanceComponents'

interface DataCleanupSectionProps {
  triggeringTask: string | null
  onTrigger: (taskName: string) => void
}

export function DataCleanupSection({
  triggeringTask,
  onTrigger,
}: DataCleanupSectionProps) {
  return (
    <>
      <SectionHeader
        title="Data Cleanup"
        icon={<Trash2 className="h-4 w-4 text-muted-foreground" />}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MaintenanceItem
          title="Old Agent Runs"
          icon={<Users className="h-5 w-5 text-accent" />}
          metrics={[{ label: 'Retention', value: '30 days' }]}
          badge={{ text: 'Weekly' }}
          schedule="Sunday 04:15 UTC"
          onTrigger={() => onTrigger('cleanup_old_agent_runs_task')}
          isTriggering={triggeringTask === 'cleanup_old_agent_runs_task'}
        />
        <MaintenanceItem
          title="Orphaned Data"
          icon={<ServerCrash className="h-5 w-5 text-status-error" />}
          metrics={[{ label: 'Type', value: 'Integrity fix' }]}
          badge={{ text: 'Weekly' }}
          schedule="Sunday 04:30 UTC"
          onTrigger={() => onTrigger('cleanup_orphaned_data_task')}
          isTriggering={triggeringTask === 'cleanup_orphaned_data_task'}
        />
        <MaintenanceItem
          title="Temp Files"
          icon={<FileX className="h-5 w-5 text-text-muted" />}
          metrics={[{ label: 'Retention', value: '24 hours' }]}
          badge={{ text: 'Daily' }}
          schedule="Daily 02:15 UTC"
          onTrigger={() => onTrigger('cleanup_temp_files_task')}
          isTriggering={triggeringTask === 'cleanup_temp_files_task'}
        />
        <MaintenanceItem
          title="Evidence Artifacts"
          icon={<Camera className="h-5 w-5 text-status-info" />}
          metrics={[{ label: 'Keep', value: '5 versions' }]}
          badge={{ text: 'Daily' }}
          schedule="Daily 06:00 UTC"
          onTrigger={() => onTrigger('cleanup_old_versions')}
          isTriggering={triggeringTask === 'cleanup_old_versions'}
        />
      </div>
    </>
  )
}
