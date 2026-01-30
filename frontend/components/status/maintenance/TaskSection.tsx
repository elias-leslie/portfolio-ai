import { PlayCircle, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { TaskStatusBadge } from './TaskStatusBadge'
import { TaskSummary } from './TaskSummary'
import { formatDate } from './utils'
import type { TaskSectionProps } from './types'

export function TaskSection({
  title,
  description,
  icon,
  lastRun,
  onTrigger,
  isLoading,
}: TaskSectionProps) {
  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {icon}
          <div>
            <h3 className="font-semibold">{title}</h3>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
        <Button size="sm" onClick={onTrigger} disabled={isLoading}>
          {isLoading ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
        </Button>
      </div>

      {lastRun ? (
        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Last run:</span>
            <TaskStatusBadge status={lastRun.status} />
          </div>
          <div className="text-sm text-muted-foreground">
            {formatDate(lastRun.startedAt)}
          </div>
          {lastRun.dryRun && (
            <Badge variant="outline" className="text-xs">
              Dry Run
            </Badge>
          )}
          {lastRun.status === 'success' && <TaskSummary summary={lastRun.summary} />}
          {lastRun.status === 'error' && lastRun.errorMessage && (
            <div className="text-sm text-loss bg-loss/10 p-2 rounded">
              {lastRun.errorMessage}
            </div>
          )}
        </div>
      ) : (
        <div className="pt-2 border-t">
          <span className="text-sm text-muted-foreground">Never run</span>
        </div>
      )}
    </div>
  )
}
