import { Wifi } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  getConnectionBadge,
} from '@/lib/utils/connectionBadge'
import type { ConnectionState } from '@/lib/utils/connectionBadge'

interface StatusHeaderActionsProps {
  realtimeEnabled: boolean
  setRealtimeEnabled: (value: boolean) => void
  connectionState: ConnectionState
  retryConnection: () => void
}

export function StatusHeaderActions({
  realtimeEnabled,
  setRealtimeEnabled,
  connectionState,
  retryConnection,
}: StatusHeaderActionsProps) {
  const connectionBadge = getConnectionBadge(connectionState, realtimeEnabled)

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2">
        <Switch
          id="realtime-toggle"
          checked={realtimeEnabled}
          onCheckedChange={setRealtimeEnabled}
        />
        <Label htmlFor="realtime-toggle" className="cursor-pointer text-sm">
          Live updates
        </Label>
      </div>

      <Badge
        variant={connectionBadge.variant}
        className="flex items-center gap-1.5"
      >
        {connectionBadge.icon}
        {connectionBadge.text}
      </Badge>

      {realtimeEnabled &&
        (connectionState === 'fallback' || connectionState === 'disconnected') && (
          <Button
            variant="outline"
            size="sm"
            onClick={retryConnection}
            className="flex items-center gap-1"
          >
            <Wifi className="h-4 w-4" />
            Retry live
          </Button>
        )}
    </div>
  )
}
