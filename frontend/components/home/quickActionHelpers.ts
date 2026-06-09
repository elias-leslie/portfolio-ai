import type { HomeActionItem } from '@/lib/api/home'

/** Button label for a Home action's quick-execute affordance. */
export function quickActionLabel(action: HomeActionItem) {
  if (!action.execution) {
    return null
  }

  switch (action.execution.kind) {
    case 'acknowledge_notification':
      return 'Dismiss alert'
    case 'workflow_transition':
      return 'Advance workflow'
    default:
      return 'Quick action'
  }
}

/** Tooltip clarifying what a Home quick action does (and does not) do. */
export function quickActionTitle(action: HomeActionItem) {
  if (action.execution?.kind === 'acknowledge_notification') {
    return 'Dismisses this Today alert only. It does not place a trade or approve the recommendation.'
  }

  return undefined
}
