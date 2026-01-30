import { Badge } from '@/components/ui/badge'

export function ImpactBadge({
  impact,
}: {
  impact: 'positive' | 'negative' | 'neutral'
}) {
  const config = {
    positive: {
      color:
        'bg-status-success/10 text-status-success border-status-success/20',
      icon: '+',
    },
    negative: {
      color: 'bg-status-error/10 text-status-error border-status-error/20',
      icon: '-',
    },
    neutral: {
      color: 'bg-surface-muted text-text-muted border-border',
      icon: '~',
    },
  }

  const { color, icon } = config[impact]

  return (
    <Badge variant="outline" className={`${color} text-xs px-1.5 py-0 h-5`}>
      {icon}
    </Badge>
  )
}
