'use client'

import { Fragment, useMemo, useState } from 'react'
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type {
  CardRewardEstimate,
  CreditStance,
  ValuationStance,
} from '@/lib/api/cards'
import { formatCurrencyWhole } from '@/lib/formatters'
import { useCardRankings } from '@/lib/hooks/useCards'
import { cn } from '@/lib/utils'
import { bucketLabel } from './cards-helpers'

type SortKey =
  | 'firstYearValue'
  | 'steadyStateValue'
  | 'welcomeValue'
  | 'annualFee'
  | 'earnValue'

const SORT_COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'firstYearValue', label: 'First-year net' },
  { key: 'steadyStateValue', label: 'Steady-state' },
  { key: 'welcomeValue', label: 'Welcome bonus' },
  { key: 'annualFee', label: 'Annual fee' },
  { key: 'earnValue', label: 'Est. category earnings' },
]

const VALUATION_STANCES: { value: ValuationStance; label: string }[] = [
  { value: 'conservative', label: 'Conservative' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'optimistic', label: 'Optimistic' },
]

const CREDIT_STANCES: { value: CreditStance; label: string }[] = [
  { value: 'easy_only', label: 'Easy credits only' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'face_value', label: 'Face value' },
]

const AMORTIZATION_OPTIONS = [1, 2, 3, 4, 5]

function StanceToggle<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (next: T) => void
  label: string
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-xs text-text-muted">{label}</span>
      {options.map((option) => (
        <Button
          key={option.value}
          type="button"
          size="sm"
          variant={value === option.value ? 'default' : 'outline'}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </Button>
      ))}
    </div>
  )
}

function netValueTone(value: number) {
  if (value > 0) return 'text-gain'
  if (value < 0) return 'text-loss'
  return 'text-text'
}

function ExpandedRow({ estimate }: { estimate: CardRewardEstimate }) {
  return (
    <TableRow className="bg-surface-muted/10 hover:bg-surface-muted/10">
      <TableCell colSpan={7}>
        <div className="space-y-3 py-2">
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
              Per-category contribution (annual)
            </p>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-6">
              {estimate.categoryContributions.map((contribution) => (
                <div
                  key={contribution.bucket}
                  className="rounded-xl border border-border/40 bg-surface-muted/20 px-3 py-2"
                >
                  <p className="text-xs text-text-muted">
                    {bucketLabel(contribution.bucket)} ·{' '}
                    {contribution.multiplier}x
                  </p>
                  <p className="font-medium tabular-nums text-text">
                    {formatCurrencyWhole(contribution.annualValue)}
                  </p>
                  <p className="text-xs text-text-muted">
                    {formatCurrencyWhole(contribution.monthlySpend)}/mo spend
                  </p>
                </div>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-text-muted">
            <span>
              Credits counted: {formatCurrencyWhole(estimate.creditsValue)}
            </span>
            <span>
              Point value assumed: {estimate.assumedPointValueCents.toFixed(2)}¢
            </span>
            <span>
              Welcome reachable:{' '}
              {estimate.welcomeReachable ? 'yes' : 'no — excluded'}
            </span>
          </div>
          {estimate.warnings.length > 0 ? (
            <ul className="space-y-1">
              {estimate.warnings.map((warning) => (
                <li key={warning} className="text-xs text-warning">
                  {warning}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </TableCell>
    </TableRow>
  )
}

export function CardRankingTable() {
  const [valuationStance, setValuationStance] =
    useState<ValuationStance>('balanced')
  const [creditStance, setCreditStance] = useState<CreditStance>('easy_only')
  const [amortizationYears, setAmortizationYears] = useState(3)
  const [sortKey, setSortKey] = useState<SortKey>('firstYearValue')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null)

  const {
    data: ranking,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useCardRankings({ valuationStance, creditStance, amortizationYears })

  const rows = useMemo(() => {
    const estimates = ranking?.byFirstYear ?? []
    const direction = sortDirection === 'asc' ? 1 : -1
    return [...estimates].sort(
      (left, right) => (left[sortKey] - right[sortKey]) * direction,
    )
  }, [ranking, sortKey, sortDirection])

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDirection(key === 'annualFee' ? 'asc' : 'desc')
    }
  }

  return (
    <SectionCard
      variant="surface"
      title="Card value ranking"
      description="Catalog cards ranked against the household's real spend profile."
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <StanceToggle
            label="Point valuation"
            options={VALUATION_STANCES}
            value={valuationStance}
            onChange={setValuationStance}
          />
          <StanceToggle
            label="Statement credits"
            options={CREDIT_STANCES}
            value={creditStance}
            onChange={setCreditStance}
          />
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-text-muted">Amortize bonus over</span>
            <Select
              value={String(amortizationYears)}
              onValueChange={(next) => setAmortizationYears(Number(next))}
            >
              <SelectTrigger className="h-9 w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AMORTIZATION_OPTIONS.map((years) => (
                  <SelectItem key={years} value={String(years)}>
                    {years} yr{years === 1 ? '' : 's'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {error && !ranking ? (
          <LoadErrorState
            title="Failed to load card rankings."
            onRetry={() => {
              void refetch()
            }}
            isRetrying={isFetching}
          />
        ) : isLoading ? (
          <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
            Ranking cards against the household spend profile…
          </div>
        ) : (
          <>
            <div className={cn(isFetching && 'opacity-60')}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Card</TableHead>
                    {SORT_COLUMNS.map((column) => (
                      <TableHead key={column.key} className="text-right">
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 hover:text-text"
                          onClick={() => toggleSort(column.key)}
                          aria-sort={
                            sortKey === column.key
                              ? sortDirection === 'asc'
                                ? 'ascending'
                                : 'descending'
                              : undefined
                          }
                        >
                          {column.label}
                          <span aria-hidden="true" className="text-xs">
                            {sortKey === column.key
                              ? sortDirection === 'asc'
                                ? '▲'
                                : '▼'
                              : ''}
                          </span>
                        </button>
                      </TableHead>
                    ))}
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((estimate) => (
                    <Fragment key={estimate.slug}>
                      <TableRow
                        className="cursor-pointer"
                        onClick={() =>
                          setExpandedSlug((current) =>
                            current === estimate.slug ? null : estimate.slug,
                          )
                        }
                      >
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="font-medium text-text">
                              {estimate.productName}
                            </span>
                            <span className="text-xs text-text-muted">
                              {estimate.issuer}
                              {estimate.cardKind !== 'personal'
                                ? ` · ${estimate.cardKind}`
                                : ''}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell
                          className={cn(
                            'text-right tabular-nums',
                            netValueTone(estimate.firstYearValue),
                          )}
                        >
                          {formatCurrencyWhole(estimate.firstYearValue)}
                        </TableCell>
                        <TableCell
                          className={cn(
                            'text-right tabular-nums',
                            netValueTone(estimate.steadyStateValue),
                          )}
                        >
                          {formatCurrencyWhole(estimate.steadyStateValue)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {estimate.welcomeValue > 0 ? (
                            <span
                              className={cn(
                                !estimate.welcomeReachable && 'line-through',
                              )}
                              title={
                                estimate.welcomeReachable
                                  ? undefined
                                  : 'Minimum spend not reachable at the current spend rate'
                              }
                            >
                              {formatCurrencyWhole(estimate.welcomeValue)}
                            </span>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatCurrencyWhole(estimate.annualFee)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatCurrencyWhole(estimate.earnValue)}
                        </TableCell>
                        <TableCell className="text-right">
                          <span className="inline-flex items-center gap-1.5">
                            {estimate.warnings.length > 0 ? (
                              <Badge variant="warning">
                                {estimate.warnings.length}
                              </Badge>
                            ) : null}
                            <span
                              aria-hidden="true"
                              className="text-xs text-text-muted"
                            >
                              {expandedSlug === estimate.slug ? '▾' : '▸'}
                            </span>
                          </span>
                        </TableCell>
                      </TableRow>
                      {expandedSlug === estimate.slug ? (
                        <ExpandedRow estimate={estimate} />
                      ) : null}
                    </Fragment>
                  ))}
                </TableBody>
              </Table>
            </div>

            {ranking ? (
              <div className="space-y-2">
                {ranking.assumptions.length > 0 ? (
                  <ul className="list-disc space-y-1 pl-5 text-xs text-text-muted">
                    {ranking.assumptions.map((assumption) => (
                      <li key={assumption}>{assumption}</li>
                    ))}
                  </ul>
                ) : null}
                <p className="rounded-xl bg-surface-muted/20 px-3 py-2 text-xs text-text-muted/80">
                  {ranking.disclaimer}
                </p>
              </div>
            ) : null}
          </>
        )}
      </div>
    </SectionCard>
  )
}
