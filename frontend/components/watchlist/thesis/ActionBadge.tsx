import { Badge } from '@/components/ui/badge'

export function ActionBadge({ action }: { action: 'BUY' | 'HOLD' | 'SELL' }) {
  const config = {
    BUY: {
      color:
        'bg-status-success/10 text-status-success border-status-success/20',
      icon: '📈',
    },
    HOLD: {
      color:
        'bg-status-warning/10 text-status-warning border-status-warning/20',
      icon: '⏸️',
    },
    SELL: {
      color: 'bg-status-error/10 text-status-error border-status-error/20',
      icon: '📉',
    },
  }

  const { color, icon } = config[action]

  return (
    <Badge className={`${color} font-semibold`}>
      <span className="mr-1">{icon}</span>
      {action}
    </Badge>
  )
}
