import { Badge } from '@/components/ui/badge'

export function SeverityBadge({
  severity,
}: {
  severity: 'high' | 'medium' | 'low'
}) {
  const config = {
    high: {
      color: 'bg-status-error/10 text-status-error border-status-error/20',
      label: 'High',
    },
    medium: {
      color:
        'bg-status-warning/10 text-status-warning border-status-warning/20',
      label: 'Med',
    },
    low: {
      color: 'bg-status-info/10 text-status-info border-status-info/20',
      label: 'Low',
    },
  }

  const { color, label } = config[severity]

  return (
    <Badge variant="outline" className={`${color} text-xs px-1.5 py-0 h-5`}>
      {label}
    </Badge>
  )
}
