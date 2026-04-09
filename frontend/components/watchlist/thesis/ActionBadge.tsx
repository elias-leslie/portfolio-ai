import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export function ActionBadge({ action }: { action: 'BUY' | 'HOLD' | 'SELL' }) {
  const config = {
    BUY: 'bg-gain/10 text-gain border-gain/20',
    HOLD: 'bg-warning/10 text-warning border-warning/20',
    SELL: 'bg-loss/10 text-loss border-loss/20',
  }

  return <Badge className={cn(config[action], 'font-semibold')}>{action}</Badge>
}
