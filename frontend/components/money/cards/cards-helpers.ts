import type { HouseholdConfirmedFact } from '@/lib/api/household'

/** Mirrors spend_alert_service DEFAULT_MONTHLY_CAP — used until a cap fact exists. */
export const DEFAULT_MONTHLY_CARD_CAP = 6500

export function playerLabel(player: string | null | undefined): string {
  if (player === 'p1') return 'Player 1'
  if (player === 'p2') return 'Player 2'
  return player ?? '—'
}

export function rotationActionLabel(action: string): string {
  switch (action) {
    case 'open_and_spend':
      return 'Open + spend'
    case 'switch_to':
      return 'Switch to'
    case 'hold':
      return 'Hold'
    default:
      return action.replaceAll('_', ' ')
  }
}

export function parseIsoDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function daysBetween(from: Date, to: Date): number {
  return Math.round((to.getTime() - from.getTime()) / 86_400_000)
}

export function formatShortDate(value: string | null | undefined): string {
  const parsed = parseIsoDate(value)
  if (!parsed) return '—'
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function isInCurrentMonth(value: string | null | undefined): boolean {
  const parsed = parseIsoDate(value)
  if (!parsed) return false
  const now = new Date()
  return (
    parsed.getFullYear() === now.getFullYear() &&
    parsed.getMonth() === now.getMonth()
  )
}

/** Per-card cap fact for the primary card, else the household default fact,
 * else $6.5k — mirrors spend_alert_service._monthly_cap. */
export function resolveMonthlyCardCap(
  facts: HouseholdConfirmedFact[],
  primaryCardId: string | null | undefined,
): number {
  const keys = primaryCardId
    ? [`card_monthly_cap:${primaryCardId}`, 'card_monthly_cap_default']
    : ['card_monthly_cap_default']
  for (const key of keys) {
    const fact = facts.find((entry) => entry.factKey === key)
    const parsed = Number(fact?.factValue)
    if (Number.isFinite(parsed) && parsed > 0) return parsed
  }
  return DEFAULT_MONTHLY_CARD_CAP
}

export function bucketLabel(bucket: string): string {
  return bucket.charAt(0).toUpperCase() + bucket.slice(1).replaceAll('_', ' ')
}
