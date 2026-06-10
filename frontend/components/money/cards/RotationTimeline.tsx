'use client'

import { useMemo } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { CreditCardProduct, RotationPlanView } from '@/lib/api/cards'
import { formatCurrencyWhole } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import { playerLabel, rotationActionLabel } from './cards-helpers'

const HORIZON_OPTIONS = [4, 8, 12]

export const PLAYER_PRESETS: {
  value: string
  label: string
  players: string[]
}[] = [
  { value: 'both', label: 'Both players', players: ['p1', 'p2'] },
  { value: 'p1', label: 'Player 1 solo', players: ['p1'] },
  { value: 'p2', label: 'Player 2 solo', players: ['p2'] },
]

function playerBadgeVariant(player: string | null | undefined) {
  return player === 'p2' ? ('secondary' as const) : ('default' as const)
}

export interface RotationTimelineProps {
  plan: RotationPlanView | undefined
  isLoading: boolean
  isFetching: boolean
  error: Error | null
  onRetry: () => void
  horizonQuarters: number
  onHorizonChange: (next: number) => void
  playerPreset: string
  onPlayerPresetChange: (next: string) => void
  catalog: CreditCardProduct[]
}

export function RotationTimeline({
  plan,
  isLoading,
  isFetching,
  error,
  onRetry,
  horizonQuarters,
  onHorizonChange,
  playerPreset,
  onPlayerPresetChange,
  catalog,
}: RotationTimelineProps) {
  const annualFeeBySlug = useMemo(() => {
    const map = new Map<string, number>()
    for (const product of catalog) {
      map.set(product.slug, product.annualFee)
    }
    return map
  }, [catalog])

  const quarters = useMemo(() => {
    if (!plan) return []
    const grouped = new Map<string, typeof plan.steps>()
    for (const step of plan.steps) {
      const existing = grouped.get(step.quarterLabel)
      if (existing) {
        existing.push(step)
      } else {
        grouped.set(step.quarterLabel, [step])
      }
    }
    return [...grouped.entries()]
  }, [plan])

  return (
    <SectionCard
      variant="surface"
      title="Rotation plan"
      description="Quarter-by-quarter card opens, alternating players to stay under issuer rules like Chase 5/24."
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-text-muted">Horizon</span>
            <Select
              value={String(horizonQuarters)}
              onValueChange={(next) => onHorizonChange(Number(next))}
            >
              <SelectTrigger className="h-9 w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HORIZON_OPTIONS.map((quartersCount) => (
                  <SelectItem key={quartersCount} value={String(quartersCount)}>
                    {quartersCount} quarters
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs text-text-muted">Players</span>
            {PLAYER_PRESETS.map((preset) => (
              <Button
                key={preset.value}
                type="button"
                size="sm"
                variant={playerPreset === preset.value ? 'default' : 'outline'}
                onClick={() => onPlayerPresetChange(preset.value)}
              >
                {preset.label}
              </Button>
            ))}
          </div>
        </div>

        {error && !plan ? (
          <LoadErrorState
            title="Failed to build the rotation plan."
            onRetry={onRetry}
            isRetrying={isFetching}
          />
        ) : isLoading || !plan ? (
          <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
            Building the rotation plan…
          </div>
        ) : (
          <div className={cn('space-y-4', isFetching && 'opacity-60')}>
            {plan.warnings.length > 0 ? (
              <div className="space-y-1 rounded-2xl border border-warning/40 bg-warning/10 px-4 py-3">
                {plan.warnings.map((warning) => (
                  <p key={warning} className="text-sm text-warning">
                    {warning}
                  </p>
                ))}
              </div>
            ) : null}

            <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
              <span className="text-text-muted">
                Projected rotation value{' '}
                <span className="font-medium text-text">
                  {formatCurrencyWhole(plan.projectedTotalValue)}
                </span>
              </span>
              <span className="text-text-muted">
                Single-card baseline{' '}
                <span className="font-medium text-text">
                  {formatCurrencyWhole(plan.baselineSingleCardValue)}
                </span>
                {plan.baselineProductSlug
                  ? ` (${plan.baselineProductSlug})`
                  : ''}
              </span>
              <span className="text-text-muted">
                Uplift{' '}
                <span
                  className={cn(
                    'font-medium',
                    plan.uplift >= 0 ? 'text-gain' : 'text-loss',
                  )}
                >
                  {formatCurrencyWhole(plan.uplift)}
                </span>
              </span>
            </div>

            <ol className="space-y-3">
              {quarters.map(([quarterLabel, steps]) => (
                <li
                  key={quarterLabel}
                  className="rounded-2xl border border-border/40 bg-surface-muted/10 px-4 py-3"
                >
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                    {quarterLabel}
                  </p>
                  <div className="space-y-2">
                    {steps.map((step) => {
                      const annualFee = step.productSlug
                        ? (annualFeeBySlug.get(step.productSlug) ?? 0)
                        : 0
                      return (
                        <div
                          key={step.sequenceIndex}
                          className="flex flex-col gap-1.5 md:flex-row md:items-center md:justify-between"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant={playerBadgeVariant(step.player)}>
                              {playerLabel(step.player)}
                            </Badge>
                            <span className="text-sm font-medium text-text">
                              {step.productName ?? 'Hold current card'}
                            </span>
                            <Badge variant="outline">
                              {rotationActionLabel(step.action)}
                            </Badge>
                            {step.action === 'open_and_spend' &&
                            annualFee > 0 ? (
                              <Badge variant="warning">
                                AF {formatCurrencyWhole(annualFee)}
                              </Badge>
                            ) : null}
                          </div>
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-muted">
                            <span>
                              Spend {formatCurrencyWhole(step.targetSpend)}
                            </span>
                            <span className="font-medium text-text">
                              +{formatCurrencyWhole(step.projectedValue)}
                            </span>
                          </div>
                        </div>
                      )
                    })}
                    {steps.flatMap((step) => step.ruleWarnings).length > 0 ? (
                      <div className="space-y-1 rounded-xl border border-warning/40 bg-warning/10 px-3 py-2">
                        {steps
                          .flatMap((step) => step.ruleWarnings)
                          .map((warning) => (
                            <p key={warning} className="text-xs text-warning">
                              {warning}
                            </p>
                          ))}
                      </div>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>

            {plan.assumptions.length > 0 ? (
              <ul className="list-disc space-y-1 pl-5 text-xs text-text-muted">
                {plan.assumptions.map((assumption) => (
                  <li key={assumption}>{assumption}</li>
                ))}
              </ul>
            ) : null}
            <p className="rounded-xl bg-surface-muted/20 px-3 py-2 text-xs text-text-muted/80">
              {plan.disclaimer}
            </p>
          </div>
        )}
      </div>
    </SectionCard>
  )
}
