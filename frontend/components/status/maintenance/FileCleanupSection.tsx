'use client'

import { Brain, Database, FileText, FolderOpen, TestTube } from 'lucide-react'
import type { FileCleanupStatusResponse } from '@/lib/api/maintenance'
import { MaintenanceItem, SectionHeader } from '../MaintenanceComponents'

interface FileCleanupSectionProps {
  fileCleanup: FileCleanupStatusResponse | null
  triggeringTask: string | null
  onTrigger: (taskName: string) => void
}

export function FileCleanupSection({
  fileCleanup,
  triggeringTask,
  onTrigger,
}: FileCleanupSectionProps) {
  const formatSize = (mb: number) => {
    if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`
    return `${mb.toFixed(2)} MB`
  }

  return (
    <>
      <SectionHeader
        title="File Cleanup"
        icon={<FolderOpen className="h-4 w-4 text-muted-foreground" />}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MaintenanceItem
          title="Application Logs"
          icon={<FileText className="h-5 w-5 text-status-warning" />}
          metrics={[
            {
              label: 'Size',
              value: formatSize(fileCleanup?.logs?.sizeMb || 0),
            },
            {
              label: 'Files',
              value: String(fileCleanup?.logs?.fileCount || 0),
            },
          ]}
          badge={{ text: fileCleanup?.logs?.retentionPolicy || 'N/A' }}
          schedule={fileCleanup?.logs?.schedule}
          onTrigger={() => onTrigger('cleanup_old_logs_task')}
          isTriggering={triggeringTask === 'cleanup_old_logs_task'}
        />
        <MaintenanceItem
          title="Database Backups"
          icon={<Database className="h-5 w-5 text-status-info" />}
          metrics={[
            {
              label: 'Size',
              value: formatSize(fileCleanup?.backups?.sizeMb || 0),
            },
            {
              label: 'Files',
              value: String(fileCleanup?.backups?.fileCount || 0),
            },
          ]}
          badge={{ text: fileCleanup?.backups?.retentionPolicy || 'N/A' }}
          schedule={fileCleanup?.backups?.schedule}
          onTrigger={() => onTrigger('cleanup_old_backups_task')}
          isTriggering={triggeringTask === 'cleanup_old_backups_task'}
        />
        <MaintenanceItem
          title="ML Model Versions"
          icon={<Brain className="h-5 w-5 text-accent" />}
          metrics={[
            {
              label: 'Size',
              value: formatSize(fileCleanup?.models?.sizeMb || 0),
            },
            {
              label: 'Files',
              value: String(fileCleanup?.models?.fileCount || 0),
            },
          ]}
          badge={{ text: fileCleanup?.models?.retentionPolicy || 'N/A' }}
          schedule={fileCleanup?.models?.schedule}
          onTrigger={() => onTrigger('cleanup_old_models_task')}
          isTriggering={triggeringTask === 'cleanup_old_models_task'}
        />
        <MaintenanceItem
          title="Test Artifacts"
          icon={<TestTube className="h-5 w-5 text-status-success" />}
          metrics={[
            {
              label: 'Size',
              value: formatSize(fileCleanup?.solutionState?.sizeMb || 0),
            },
            {
              label: 'Files',
              value: String(fileCleanup?.solutionState?.fileCount || 0),
            },
          ]}
          badge={{
            text: fileCleanup?.solutionState?.retentionPolicy || 'N/A',
          }}
          schedule={fileCleanup?.solutionState?.schedule}
          onTrigger={() => onTrigger('cleanup_solution_state_task')}
          isTriggering={triggeringTask === 'cleanup_solution_state_task'}
        />
      </div>
    </>
  )
}
