import { AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface TaskStatusBadgeProps {
  status: string
}

export function TaskStatusBadge({ status }: TaskStatusBadgeProps) {
  switch (status) {
    case 'success':
      return (
        <Badge variant="default" className="flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3" />
          Success
        </Badge>
      )
    case 'error':
      return (
        <Badge variant="destructive" className="flex items-center gap-1">
          <AlertCircle className="h-3 w-3" />
          Error
        </Badge>
      )
    case 'running':
      return (
        <Badge variant="secondary" className="flex items-center gap-1">
          <RefreshCw className="h-3 w-3 animate-spin" />
          Running
        </Badge>
      )
    default:
      return <Badge variant="secondary">Unknown</Badge>
  }
}
