import { AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export function StatusBadge({
  status,
  isRunning,
}: {
  status: string
  isRunning?: boolean
}) {
  if (isRunning) {
    return (
      <Badge className="flex items-center gap-1 bg-status-info text-text-inverted animate-pulse">
        <RefreshCw className="h-3 w-3 animate-spin" />
        Running
      </Badge>
    )
  }

  switch (status) {
    case 'success':
      return (
        <Badge className="flex items-center gap-1 bg-status-success text-text-inverted">
          <CheckCircle2 className="h-3 w-3" />
          Success
        </Badge>
      )
    case 'error':
      return (
        <Badge className="flex items-center gap-1 bg-status-error text-text-inverted">
          <AlertCircle className="h-3 w-3" />
          Error
        </Badge>
      )
    default:
      return <Badge variant="secondary">Unknown</Badge>
  }
}
