import type { HouseholdAccountSummary } from '@/lib/api/household'
import { formatDate, formatRelativeTime } from '@/lib/utils'

export const freshnessTone = {
  fresh: 'border-gain/25 bg-gain/5 text-gain',
  aging: 'border-warning/25 bg-warning/5 text-warning',
  stale: 'border-loss/25 bg-loss/5 text-loss',
  needs_evidence: 'border-primary/25 bg-primary/5 text-primary',
  not_applicable: 'border-border/40 bg-surface/70 text-text-muted',
}

export function freshnessToneClass(status: string | null | undefined) {
  return (
    freshnessTone[status as keyof typeof freshnessTone] ??
    freshnessTone.needs_evidence
  )
}

/** Map freshnessToneClass tones onto the shared Badge variants. */
export function freshnessBadgeVariant(status: string | null | undefined) {
  switch (status) {
    case 'fresh':
      return 'success' as const
    case 'aging':
      return 'warning' as const
    case 'stale':
      return 'error' as const
    case 'not_applicable':
      return 'outline' as const
    default:
      return 'default' as const
  }
}

export function accountMetaLine(account: HouseholdAccountSummary) {
  const parts = [account.assetGroup]
  // Skip the type when it just repeats the asset group ("retirement · retirement").
  if (account.accountType !== account.assetGroup) {
    parts.push(account.accountType.replaceAll('_', ' '))
  }
  if (account.institutionName) parts.push(account.institutionName)
  if (account.ownerName) parts.push(account.ownerName)
  return parts.join(' · ')
}

export function accountSubline(account: HouseholdAccountSummary) {
  if (account.evidenceCount === 0) return 'Awaiting evidence'
  return account.evidenceCount === 1
    ? '1 supporting document'
    : `${account.evidenceCount} supporting documents`
}

export function accountCoverageDetail(
  account: HouseholdAccountSummary,
  topGap: HouseholdAccountSummary['gapFlags'][number] | null,
) {
  const pricedPositionCount = account.pricedPositionCount ?? 0
  return [
    topGap ? `${topGap.title}: ${topGap.detail}` : null,
    `Balance ${account.balanceFreshnessLabel.toLowerCase()}`,
    account.moneyRole === 'spend_driver'
      ? `Transactions ${account.transactionFreshnessLabel.toLowerCase()}`
      : 'Transactions not required',
    pricedPositionCount > 0
      ? `${(account.quoteFreshnessLabel ?? 'live quotes').toLowerCase()} across ${pricedPositionCount} priced position${pricedPositionCount === 1 ? '' : 's'}`
      : null,
    account.lastEvidenceAt
      ? `Last evidence ${formatRelativeTime(account.lastEvidenceAt)}`
      : 'No evidence yet',
    `${account.evidenceCount} source${account.evidenceCount === 1 ? '' : 's'}`,
  ]
    .filter(Boolean)
    .join(' · ')
}

export function moneyRoleLabel(role: string) {
  return role === 'spend_driver' ? 'Spending account' : 'Net worth only'
}

export function accountEvidenceDate(
  value: string | null | undefined,
  daysSince: number | null | undefined,
) {
  if (!value) return 'missing'
  const ageLabel = daysSince == null ? null : `${daysSince}d old`
  return `${formatDate(value)}${ageLabel ? ` (${ageLabel})` : ''}`
}
