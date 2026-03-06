'use client'

import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useQueueDepth } from '@/lib/hooks/useCeleryTasks'

export function QueueDepthCard() {
  const { data, refetch, isLoading, isFetching } = useQueueDepth()

  const getStatusColor = (depth: number) => {
    if (depth === 0) return 'text-gain'
    if (depth < 50) return 'text-accent'
    if (depth < 100) return 'text-warning'
    return 'text-loss'
  }

  const getStatusIcon = (depth: number) => {
    if (depth === 0) return <CheckCircle className="h-5 w-5 text-gain" />
    if (depth < 50) return <CheckCircle className="h-5 w-5 text-accent" />
    if (depth < 100) return <AlertTriangle className="h-5 w-5 text-warning" />
    return <AlertCircle className="h-5 w-5 text-loss" />
  }

  const getStatusMessage = (depth: number, consumers: number) => {
    if (depth === 0) return 'Queue is empty'
    if (depth < 50)
      return `${depth} tasks pending across ${consumers} worker${consumers !== 1 ? 's' : ''}`
    if (depth < 100) return `⚠️ ${depth} tasks pending - queue building up`
    return `🚨 ${depth} tasks pending - queue overloaded!`
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div>
          <CardTitle className="text-lg">Queue Depth</CardTitle>
          <CardDescription>Pending workflow queue status</CardDescription>
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
            Click refresh to load queue depth
          </div>
        ) : isLoading ? (
          <div className="text-center py-4 text-muted-foreground text-sm">
            Loading...
          </div>
        ) : data ? (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              {getStatusIcon(data.depth)}
              <div>
                <div
                  className={`text-3xl font-bold ${getStatusColor(data.depth)}`}
                >
                  {data.depth}
                </div>
                <div className="text-sm text-muted-foreground">
                  {getStatusMessage(data.depth, data.consumers)}
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
