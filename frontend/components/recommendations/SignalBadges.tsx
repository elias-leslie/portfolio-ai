import {
  AlertTriangle,
  BarChart3,
  FileText,
  Sparkles,
  Star,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export function SignalBadge({
  type,
  strength,
}: {
  type: string
  strength: number
}) {
  if (type === 'BUY') {
    return (
      <Badge className="bg-gain text-text-inverted">
        <TrendingUp className="mr-1 h-3 w-3" />
        BUY {strength}/10
      </Badge>
    )
  }
  if (type === 'SELL') {
    return (
      <Badge className="bg-loss text-text-inverted">
        <TrendingDown className="mr-1 h-3 w-3" />
        SELL {strength}/10
      </Badge>
    )
  }
  return <Badge variant="outline">HOLD {strength}/10</Badge>
}

export function SignalStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'better_entry':
      return (
        <Badge className="bg-gain text-text-inverted">
          <Sparkles className="mr-1 h-3 w-3" />
          Better Entry
        </Badge>
      )
    case 'caution':
      return (
        <Badge className="bg-warning text-text-inverted">
          <AlertTriangle className="mr-1 h-3 w-3" />
          Caution
        </Badge>
      )
    default:
      return null // Don't show badge for "valid" status
  }
}

export function ValidationBadge({
  validationType,
}: {
  validationType: 'thesis' | 'backtest' | 'both'
}) {
  switch (validationType) {
    case 'thesis':
      return (
        <Badge
          className="bg-primary text-primary-foreground"
          title="Event-Driven: Validated by investment thesis"
        >
          <FileText className="mr-1 h-3 w-3" />
          Thesis
        </Badge>
      )
    case 'backtest':
      return (
        <Badge
          className="bg-accent text-accent-foreground"
          title="Technical: Validated by backtest (Sharpe >= 1.0)"
        >
          <BarChart3 className="mr-1 h-3 w-3" />
          Technical
        </Badge>
      )
    case 'both':
      return (
        <Badge
          className="bg-warning text-text-inverted"
          title="Highest confidence: Both thesis AND backtest validated"
        >
          <Star className="mr-1 h-3 w-3" />
          Both
        </Badge>
      )
  }
}
