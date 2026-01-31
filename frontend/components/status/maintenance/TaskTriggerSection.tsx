import { PlayCircle, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { MaintenanceResult } from '@/lib/api/maintenance'
import { StatusBadge } from './StatusBadge'
import { formatDateTime } from './utils'

interface TaskTriggerSectionProps {
  title: string
  description: string
  icon: React.ReactNode
  lastRun: MaintenanceResult | null
  onTrigger: () => void
  isLoading: boolean
}

export function TaskTriggerSection({
  title,
  description,
  icon,
  lastRun,
  onTrigger,
  isLoading,
}: TaskTriggerSectionProps) {
  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3 flex-1">
          {icon}
          <div>
            <h3 className="font-semibold text-sm">{title}</h3>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
        </div>
        <Button
          size="sm"
          onClick={onTrigger}
          disabled={isLoading}
          variant="outline"
        >
          {isLoading ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
          <span className="ml-1 hidden sm:inline">Trigger</span>
        </Button>
      </div>

      {lastRun ? (
        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Last run</span>
            <StatusBadge status={lastRun.status} />
          </div>
          <div className="text-xs text-muted-foreground">
            {formatDateTime(lastRun.startedAt)}
          </div>
          {lastRun.dryRun && (
            <Badge variant="outline" className="text-xs">
              Dry Run
            </Badge>
          )}
          {lastRun.status === 'error' && lastRun.errorMessage && (
            <div className="text-xs text-loss bg-loss/10 p-2 rounded">
              {lastRun.errorMessage}
            </div>
          )}
        </div>
      ) : (
        <div className="pt-2 border-t">
          <span className="text-xs text-muted-foreground">Never run</span>
        </div>
      )}
    </div>
  )
}
