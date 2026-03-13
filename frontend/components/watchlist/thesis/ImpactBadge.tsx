import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export function ImpactBadge({
  impact,
}: {
  impact: 'positive' | 'negative' | 'neutral'
}) {
  const config = {
    positive: {
      color: 'bg-gain/10 text-gain border-gain/20',
      icon: '+',
    },
    negative: {
      color: 'bg-loss/10 text-loss border-loss/20',
      icon: '-',
    },
    neutral: {
      color: 'bg-surface-muted text-text-muted border-border',
      icon: '~',
    },
  }

  const { color, icon } = config[impact]

  return (
    <Badge variant="outline" className={cn(color, 'text-xs px-1.5 py-0 h-5')}>
      {icon}
    </Badge>
  )
}
