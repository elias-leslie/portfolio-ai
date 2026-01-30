import { ChevronDown, ChevronRight, Clock, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { formatRelativeTime } from '@/lib/utils'
import { type ScheduledTask } from './types'
import { formatDateTime } from './utils'

export function ScheduledTasksCard({
  tasks,
  isLoading,
}: {
  tasks: ScheduledTask[] | null
  isLoading: boolean
}) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (isLoading && !tasks) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Scheduled Tasks
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!tasks || tasks.length === 0) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Scheduled Tasks
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No scheduled tasks available
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          <span>Scheduled Tasks</span>
          <Badge variant="secondary" className="ml-auto">
            {tasks.length} tasks
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
          <CollapsibleTrigger asChild>
            <Button variant="outline" className="w-full justify-between">
              <span>View all scheduled tasks</span>
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-4 space-y-3">
              {tasks.map((task) => (
                <div
                  key={task.name}
                  className="border rounded-lg p-3 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-sm">{task.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {task.description}
                      </p>
                    </div>
                    <Badge variant="outline" className="font-mono text-xs">
                      {task.schedule}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <p className="text-muted-foreground">Last run</p>
                      <p className="font-mono">
                        {formatRelativeTime(task.lastRun)}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Next run</p>
                      <p className="font-mono">
                        {formatDateTime(task.nextRun)}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  )
}
