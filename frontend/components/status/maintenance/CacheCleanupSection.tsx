'use client'

import { Loader2, Trash2, Zap } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { CacheStatusResponse } from '@/lib/api/maintenance'
import { SectionHeader } from '../MaintenanceComponents'

interface CacheCleanupSectionProps {
  cacheStatus: CacheStatusResponse | null
  triggeringTask: string | null
  onTrigger: (taskName: string) => void
}

export function CacheCleanupSection({
  cacheStatus,
  triggeringTask,
  onTrigger,
}: CacheCleanupSectionProps) {
  const formatSize = (mb: number) => {
    if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`
    return `${mb.toFixed(2)} MB`
  }

  return (
    <>
      <SectionHeader
        title="Cache Cleanup (Optional)"
        icon={<Zap className="h-4 w-4 text-muted-foreground" />}
      />
      <Card className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Zap className="h-5 w-5 text-status-warning" />
              <span className="font-medium">Development Caches</span>
              <Badge variant="outline" className="text-xs">
                Manual only
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              Python bytecode, linter caches, and build caches. Safe to delete -
              they regenerate automatically.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onTrigger('cleanup_cache_directories_task')}
            disabled={triggeringTask === 'cleanup_cache_directories_task'}
            title="Clean all development caches"
          >
            {triggeringTask === 'cleanup_cache_directories_task' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </Button>
        </div>
        {cacheStatus && cacheStatus.directories.length > 0 && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm font-medium border-b pb-2">
              <span>Total: {formatSize(cacheStatus.totalSizeMb)}</span>
              <span>{cacheStatus.totalFileCount.toLocaleString()} files</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {cacheStatus.directories
                .filter((d) => d.sizeMb > 0)
                .map((dir) => (
                  <div key={dir.path} className="text-xs border rounded p-2">
                    <div className="font-medium truncate" title={dir.name}>
                      {dir.name}
                    </div>
                    <div className="flex justify-between text-muted-foreground">
                      <span>{formatSize(dir.sizeMb)}</span>
                      <span>{dir.fileCount.toLocaleString()} files</span>
                    </div>
                  </div>
                ))}
            </div>
            {cacheStatus.directories.every((d) => d.sizeMb === 0) && (
              <div className="text-sm text-muted-foreground text-center py-2">
                All caches are empty
              </div>
            )}
          </div>
        )}
      </Card>
    </>
  )
}
