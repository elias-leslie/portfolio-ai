'use client'

import { Clock, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useBeatSchedule } from '@/lib/hooks/useCeleryTasks'

export function BeatScheduleCard() {
  const { data, refetch, isLoading, isFetching } = useBeatSchedule()

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div>
          <CardTitle className="text-lg">Beat Schedule</CardTitle>
          <CardDescription>Celery periodic tasks</CardDescription>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading || isFetching}
        >
          <RefreshCw
            className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`}
          />
        </Button>
      </CardHeader>
      <CardContent>
        {!data && !isLoading ? (
          <div className="text-center py-4 text-muted-foreground text-sm">
            Click refresh to load schedule
          </div>
        ) : isLoading ? (
          <div className="text-center py-4 text-muted-foreground text-sm">
            Loading...
          </div>
        ) : data && data.length === 0 ? (
          <div className="text-center py-4 text-muted-foreground text-sm">
            No scheduled tasks found
          </div>
        ) : data ? (
          <div className="space-y-3">
            {data.map((task, index) => (
              <div
                key={index}
                className="flex items-start gap-3 border-b last:border-0 pb-3 last:pb-0"
              >
                <Clock className="h-4 w-4 text-muted-foreground mt-1" />
                <div className="flex-1 space-y-1">
                  <div className="font-medium text-sm">{task.name}</div>
                  <div className="text-xs text-muted-foreground font-mono">
                    {task.task}
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {task.schedule}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
