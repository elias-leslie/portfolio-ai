import { Badge } from '@/components/ui/badge'

export function ActionBadge({ action }: { action: 'BUY' | 'HOLD' | 'SELL' }) {
  const config = {
    BUY: {
      color: 'bg-gain/10 text-gain border-gain/20',
      icon: '📈',
    },
    HOLD: {
      color: 'bg-warning/10 text-warning border-warning/20',
      icon: '⏸️',
    },
    SELL: {
      color: 'bg-loss/10 text-loss border-loss/20',
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
