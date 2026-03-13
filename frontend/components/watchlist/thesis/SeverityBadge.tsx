import { Badge } from '@/components/ui/badge'

export function SeverityBadge({
  severity,
}: {
  severity: 'high' | 'medium' | 'low'
}) {
  const config = {
    high: {
      color: 'bg-loss/10 text-loss border-loss/20',
      label: 'High',
    },
    medium: {
      color: 'bg-warning/10 text-warning border-warning/20',
      label: 'Med',
    },
    low: {
      color: 'bg-accent/10 text-accent border-accent/20',
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
