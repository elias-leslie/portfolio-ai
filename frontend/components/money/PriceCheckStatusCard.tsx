'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HouseholdPriceCheckRun } from '@/lib/api/household'
import { formatEnumLabel } from '@/lib/formatters'

interface PriceCheckStatusCardProps {
  latestRun: HouseholdPriceCheckRun | null | undefined
  onRun: () => void
  isTriggering: boolean
}

const runBadgeVariant = (
  status: HouseholdPriceCheckRun['status'],
): 'default' | 'success' | 'destructive' | 'warning' => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'destructive'
  return 'warning'
}

const vendorBadgeVariant = (
  status: string,
): 'default' | 'success' | 'destructive' | 'warning' => {
  if (status === 'ok') return 'success'
  if (status === 'error') return 'destructive'
  return 'warning'
}

function formatRunTime(value: string | null | undefined): string | null {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function PriceCheckStatusCard({
  latestRun,
  onRun,
  isTriggering,
}: PriceCheckStatusCardProps) {
  const isActive =
    latestRun?.status === 'queued' || latestRun?.status === 'running'
  const runTime = formatRunTime(latestRun?.finishedAt ?? latestRun?.startedAt)

  return (
    <div className="rounded-2xl border border-border/40 bg-surface/45 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {latestRun ? (
            <>
              <Badge variant={runBadgeVariant(latestRun.status)}>
                {formatEnumLabel(latestRun.status)}
              </Badge>
              <span className="text-sm text-text-muted">
                {isActive
                  ? 'Jenny is checking vendor prices…'
                  : `Last run${runTime ? ` ${runTime}` : ''} · ${latestRun.productCount} products · ${latestRun.quoteCount} quotes · ${latestRun.findingCount} findings`}
              </span>
            </>
          ) : (
            <span className="text-sm text-text-muted">
              No price check has run yet.
            </span>
          )}
        </div>
        <Button
          type="button"
          size="sm"
          onClick={onRun}
          disabled={isTriggering || isActive}
        >
          {isActive ? 'Running…' : 'Run price check'}
        </Button>
      </div>
      {latestRun && latestRun.vendors.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {latestRun.vendors.map((vendor) => (
            <span
              key={vendor.vendorKey}
              className="flex items-center gap-1.5 text-xs text-text-muted"
            >
              <Badge variant={vendorBadgeVariant(vendor.status)}>
                {formatEnumLabel(vendor.vendorKey)}
              </Badge>
              {vendor.status === 'ok'
                ? `${vendor.quoteCount} quote${vendor.quoteCount === 1 ? '' : 's'}`
                : formatEnumLabel(vendor.status)}
            </span>
          ))}
        </div>
      )}
      {latestRun?.error && (
        <p className="mt-3 text-xs text-loss">{latestRun.error}</p>
      )}
    </div>
  )
}
