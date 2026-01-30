'use client'

import { HardDrive } from 'lucide-react'
import { Card } from '@/components/ui/card'
import type {
  CacheStatusResponse,
  DatabaseSizeResponse,
  DiskSpaceResponse,
  FileCleanupStatusResponse,
} from '@/lib/api/maintenance'
import { SectionHeader } from '../MaintenanceComponents'

interface SystemStatusSectionProps {
  fileCleanup: FileCleanupStatusResponse | null
  dbSize: DatabaseSizeResponse | null
  cacheStatus: CacheStatusResponse | null
  diskSpace: DiskSpaceResponse | null
}

export function SystemStatusSection({
  fileCleanup,
  dbSize,
  cacheStatus,
  diskSpace,
}: SystemStatusSectionProps) {
  const formatSize = (mb: number) => {
    if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`
    return `${mb.toFixed(2)} MB`
  }

  return (
    <>
      <SectionHeader
        title="System Status"
        icon={<HardDrive className="h-4 w-4 text-muted-foreground" />}
      />
      <Card className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold">
              {formatSize(fileCleanup?.totalSizeMb || 0)}
            </div>
            <div className="text-xs text-muted-foreground">Managed Files</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">
              {formatSize(dbSize?.databaseSizeMb || 0)}
            </div>
            <div className="text-xs text-muted-foreground">Database</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">
              {formatSize(cacheStatus?.totalSizeMb || 0)}
            </div>
            <div className="text-xs text-muted-foreground">Dev Caches</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">
              {diskSpace?.partitions?.[0]?.usedPercentage?.toFixed(0) || '—'}%
            </div>
            <div className="text-xs text-muted-foreground">Disk Used</div>
          </div>
        </div>
      </Card>
    </>
  )
}
