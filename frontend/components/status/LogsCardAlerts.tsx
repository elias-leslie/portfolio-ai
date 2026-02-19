'use client'

import { Filter, RefreshCw } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

interface LogsCardAlertsProps {
  restartRequired: boolean
  restartPending: boolean
  error: Error | null
  onRestartServices: () => void
}

export function LogsCardAlerts({
  restartRequired,
  restartPending,
  error,
  onRestartServices,
}: LogsCardAlertsProps) {
  return (
    <>
      {restartRequired && !restartPending && (
        <Alert className="mb-0">
          <AlertDescription>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-warning" />
                <span>
                  Log level changed. Restart services to apply the new level.
                </span>
              </div>
              <Button
                variant="default"
                size="sm"
                onClick={onRestartServices}
              >
                Restart Services
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {restartPending && (
        <Alert className="mb-0">
          <AlertDescription>
            <div className="flex items-center gap-2">
              <RefreshCw className="h-4 w-4 animate-spin" />
              <span>
                Restarting services... This will take about 10 seconds.
              </span>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive" className="mb-0">
          <AlertDescription>
            Failed to load unified logs. Check service status.
          </AlertDescription>
        </Alert>
      )}
    </>
  )
}
