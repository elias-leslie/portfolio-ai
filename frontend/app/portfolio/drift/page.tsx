'use client'

export const dynamic = 'force-dynamic'

import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  Compass,
  ExternalLink,
} from 'lucide-react'
import { useState } from 'react'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  type DriftReport,
  type DriftRow,
  fetchDriftReport,
} from '@/lib/api/drift'

const FRIENDLY_LABELS: Record<string, string> = {
  us_equity: 'US stocks',
  intl_equity: 'Foreign stocks',
  bonds: 'Bonds',
  cash: 'Cash',
  alts: 'Alternatives',
  real_estate: 'Real estate',
  unclassified: 'Unclassified',
}

function friendly(assetClass: string): string {
  return FRIENDLY_LABELS[assetClass] ?? assetClass
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function formatSignedPct(value: number): string {
  const formatted = `${(value * 100).toFixed(1)}%`
  return value > 0 ? `+${formatted}` : formatted
}

function formatMoney(value: number): string {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

interface DriftBarProps {
  row: DriftRow
}

function DriftBar({ row }: DriftBarProps) {
  // Render a horizontal bar with target marker and actual position.
  // Range spans -band*2 .. +band*2 (or +/- 30% if no band) so users see
  // how close to the edge they are without losing the relative scale.
  const span = Math.max(0.3, (row.driftBandPct || 0.05) * 4)
  const center = 50
  const offset = Math.max(-span, Math.min(span, row.driftPct)) / span
  const actualLeft = `${center + offset * 50}%`
  const bandStartPct = `${center - (row.driftBandPct / span) * 50}%`
  const bandEndPct = `${center + (row.driftBandPct / span) * 50}%`

  return (
    <div className="relative h-2 rounded-full bg-muted/40">
      <div
        className="absolute h-full rounded-full bg-emerald-100 dark:bg-emerald-900/30"
        style={{ left: bandStartPct, right: `calc(100% - ${bandEndPct})` }}
        aria-hidden
      />
      <div
        className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-foreground shadow"
        style={{ left: actualLeft }}
        aria-hidden
      />
      <div
        className="absolute top-0 h-full w-px bg-foreground/40"
        style={{ left: '50%' }}
        aria-hidden
      />
    </div>
  )
}

interface DriftRowCardProps {
  row: DriftRow
}

function DriftRowCard({ row }: DriftRowCardProps) {
  const direction = row.driftPct > 0 ? 'over' : 'under'
  const tone = row.outOfBand
    ? 'text-amber-700 dark:text-amber-400'
    : 'text-emerald-700 dark:text-emerald-400'
  return (
    <div className="space-y-3 rounded-lg border bg-card/50 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">
            {friendly(row.assetClass)}
          </div>
          <div className="text-xs text-muted-foreground">
            Goal {formatPct(row.targetPct)} · You have{' '}
            {formatPct(row.actualPct)}
          </div>
        </div>
        <div className={`text-right text-sm font-semibold ${tone}`}>
          {formatSignedPct(row.driftPct)}
          <div className="text-xs font-normal text-muted-foreground">
            {row.outOfBand
              ? `${direction} by more than wiggle room`
              : 'on plan'}
          </div>
        </div>
      </div>
      <DriftBar row={row} />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Wiggle room ±{formatPct(row.driftBandPct)}</span>
        <span>
          {formatMoney(row.actualValue)} of {formatMoney(row.targetValue)}
        </span>
      </div>
    </div>
  )
}

interface DriftPageContentProps {
  scopeId: string
}

function DriftPageContent({ scopeId }: DriftPageContentProps) {
  const { data, isLoading, error } = useQuery<DriftReport>({
    queryKey: ['portfolio', 'drift', scopeId],
    queryFn: () => fetchDriftReport('household', scopeId),
    staleTime: 1000 * 60 * 5,
  })

  if (isLoading) {
    return (
      <div className="text-sm text-muted-foreground">
        Loading your allocation…
      </div>
    )
  }
  if (error) {
    return (
      <Card>
        <CardContent className="space-y-2 p-6">
          <div className="text-sm font-semibold">
            Couldn't load your allocation
          </div>
          <div className="text-xs text-muted-foreground">
            {(error as Error).message}
          </div>
        </CardContent>
      </Card>
    )
  }
  if (!data) {
    return null
  }

  const oobCount = data.rows.filter((r) => r.outOfBand).length
  const onPlan = oobCount === 0
  const StatusIcon = onPlan ? CheckCircle2 : AlertTriangle
  const statusTone = onPlan
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-amber-600 dark:text-amber-400'

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Compass className="h-5 w-5" /> How am I doing on my goals?
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Snapshot for {data.snapshotDate}. Total value{' '}
            <span className="font-semibold text-foreground">
              {formatMoney(data.totalValue)}
            </span>
            .
          </p>
        </CardHeader>
        <CardContent className="space-y-2">
          <div
            className={`flex items-center gap-2 text-sm font-medium ${statusTone}`}
          >
            <StatusIcon className="h-4 w-4" />
            {onPlan
              ? 'You are on plan — every type of investment is inside its wiggle room.'
              : `${oobCount} ${oobCount === 1 ? 'type of investment is' : 'types of investment are'} outside their wiggle room.`}
          </div>
          {data.classesMissingTargets.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
              You hold {data.classesMissingTargets.map(friendly).join(', ')} but
              no goal is set for{' '}
              {data.classesMissingTargets.length === 1 ? 'it' : 'them'}. Add a
              target to see drift.
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-2">
        {data.rows.map((row) => (
          <DriftRowCard key={row.assetClass} row={row} />
        ))}
      </div>

      {data.rows.length === 0 && (
        <Card>
          <CardContent className="space-y-3 p-6 text-sm">
            <div className="font-semibold">No goals set yet.</div>
            <p className="text-muted-foreground">
              Set allocation goals (for example, 60% US stocks · 20% foreign
              stocks · 20% bonds) and this page will show how far off you are at
              any time.
            </p>
            <p className="text-xs text-muted-foreground">
              Goals can be set via{' '}
              <code className="rounded bg-muted px-1 py-0.5">
                st portfolio ips set
              </code>
              .
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default function DriftPage() {
  // Single-household v1 — scope_id is a literal until household selection
  // gets wired through the navigation. The household scope already
  // pre-aggregates every linked account.
  const [scopeId] = useState<string>('default')

  return (
    <PageContainer>
      <PageHeader
        title="How am I doing on my goals?"
        description="Allocation goals, how far off you are, and trades to get back on plan."
        actions={
          <Badge variant="outline" className="gap-1 text-xs font-normal">
            <ExternalLink className="h-3 w-3" />
            also via st portfolio drift
          </Badge>
        }
      />
      <DriftPageContent scopeId={scopeId} />
    </PageContainer>
  )
}
