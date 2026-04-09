import type { SymbolDecisionSection } from '@/lib/api/symbols'

export function formatDecisionSeverity(value?: string | null): string | null {
  if (!value) {
    return null
  }

  const normalized = value.replace(/_/g, ' ').toLowerCase()
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

export function formatDecisionMeta(
  decision?: Pick<
    SymbolDecisionSection,
    'sourceLabel' | 'severity' | 'sourceTimestamp'
  > | null,
  options?: { includeTimestamp?: boolean },
): string | null {
  if (!decision) {
    return null
  }

  const parts = [
    decision.sourceLabel,
    formatDecisionSeverity(decision.severity),
    options?.includeTimestamp === false
      ? null
      : (decision.sourceTimestamp ?? null),
  ].filter((part): part is string => Boolean(part))

  return parts.length > 0 ? parts.join(' · ') : null
}
