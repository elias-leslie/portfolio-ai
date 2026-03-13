import { Badge } from '@/components/ui/badge'

// Note: status values are snake_case from backend (string values aren't transformed)
export function StatusBadge({
  status,
}: {
  status: 'active' | 'invalidated' | 'flagged_for_review'
}) {
  const config = {
    active: {
      color: 'bg-accent/10 text-accent border-accent/20',
      label: 'Active',
    },
    invalidated: {
      color: 'bg-surface-muted text-text-muted border-border',
      label: 'Invalidated',
    },
    flagged_for_review: {
      color: 'bg-warning/10 text-warning border-warning/20',
      label: 'Flagged',
    },
  }

  const { color, label } = config[status]

  return (
    <Badge variant="outline" className={color}>
      {label}
    </Badge>
  )
}
