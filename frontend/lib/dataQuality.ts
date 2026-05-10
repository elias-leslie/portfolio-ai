import type { ComponentProps } from 'react'
import type { Badge } from '@/components/ui/badge'

export type DataQualityStatus =
  | 'current'
  | 'estimated'
  | 'aging'
  | 'known'
  | 'stale'
  | 'unavailable'

type BadgeVariant = ComponentProps<typeof Badge>['variant']

const RAW_TO_NORMALIZED: Record<string, DataQualityStatus> = {
  trusted: 'current',
  fresh: 'current',
  current: 'current',
  partial: 'estimated',
  estimated: 'estimated',
  aging: 'aging',
  known: 'known',
  stale: 'stale',
  blocked: 'unavailable',
  unavailable: 'unavailable',
}

export function normalizeQualityStatus(
  status: string | null | undefined,
): DataQualityStatus {
  if (!status) return 'unavailable'
  return RAW_TO_NORMALIZED[status] ?? 'unavailable'
}

export function qualityLabel(status: string | null | undefined): string {
  switch (normalizeQualityStatus(status)) {
    case 'current':
      return 'Current'
    case 'estimated':
      return 'Estimate'
    case 'aging':
      return 'Recent'
    case 'known':
      return 'Known'
    case 'stale':
      return 'Stale'
    default:
      return 'Unavailable'
  }
}

export function qualityBadgeVariant(
  status: string | null | undefined,
): BadgeVariant {
  switch (normalizeQualityStatus(status)) {
    case 'current':
      return 'success'
    case 'estimated':
    case 'aging':
      return 'warning'
    case 'known':
    case 'stale':
      return 'secondary'
    default:
      return 'outline'
  }
}

/**
 * Net-worth tiles collapse the full vocabulary into Current / Known / Unavailable —
 * the user only needs to know whether it's live, last-known, or absent.
 */
export function netWorthBadgeLabel(status: string | null | undefined): string {
  switch (normalizeQualityStatus(status)) {
    case 'current':
      return 'Current'
    case 'estimated':
    case 'known':
    case 'stale':
      return 'Known'
    default:
      return 'Unavailable'
  }
}

export function netWorthBadgeVariant(
  status: string | null | undefined,
): BadgeVariant {
  switch (normalizeQualityStatus(status)) {
    case 'current':
      return 'success'
    case 'estimated':
    case 'known':
    case 'stale':
      return 'secondary'
    default:
      return 'outline'
  }
}

export function spendPaceBadgeVariant(
  status: string | null | undefined,
): BadgeVariant {
  switch ((status ?? '').toLowerCase()) {
    case 'on_track':
    case 'within_plan':
    case 'under_plan':
      return 'success'
    case 'above_plan':
    case 'over_plan':
    case 'watch':
      return 'warning'
    default:
      return 'outline'
  }
}

export function metricToneClasses(tone: string | null | undefined): string {
  switch (tone) {
    case 'positive':
      return 'border-gain/25 bg-gain/8'
    case 'negative':
      return 'border-loss/25 bg-loss/8'
    case 'warning':
      return 'border-warning/25 bg-warning/8'
    default:
      return 'border-border/30 bg-background/25'
  }
}
