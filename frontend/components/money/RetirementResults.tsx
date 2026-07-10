'use client'

import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { freshnessToneClass } from '@/components/money/moneyAccountsUtils'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type {
  RetirementAccountRule,
  RetirementPreview,
} from '@/lib/api/household'
import { formatCurrency, formatCurrencyWhole } from '@/lib/formatters'
import {
  bucketColors,
  bucketLabel,
  bucketMapValue,
  bucketOrder,
  currencyTooltip,
  percentPoints,
  taxAssumptionText,
  taxAssumptionTooltip,
  taxAssumptionWarnings,
} from './retirement-planner-model'

type ProjectionPoint = {
  age: number
  p10: number | null
  p50: number | null
  p90: number | null
}

export function RetirementResults({
  preview,
  previewError,
  onRetry,
  isFetching,
  hasPendingChanges,
  projectionData,
  fullRetirementAge,
  drawdownBasis,
  setDrawdownBasis,
}: {
  preview: RetirementPreview | undefined
  previewError: Error | null
  onRetry: () => void
  isFetching: boolean
  hasPendingChanges: boolean
  projectionData: ProjectionPoint[]
  fullRetirementAge: number
  drawdownBasis: 'real' | 'nominal'
  setDrawdownBasis: (basis: 'real' | 'nominal') => void
}) {
  const taxWarnings = taxAssumptionWarnings(preview?.taxAssumptions)
  const taxEstimateTooltip = taxAssumptionTooltip(
    preview?.taxAssumptions,
    taxWarnings,
  )
  const balanceData = useMemo(
    () =>
      (preview?.drawdownSchedule ?? []).map((row) => ({
        age: row.primaryAge,
        cash: bucketMapValue(row.balancesByBucket, 'cash'),
        taxable: bucketMapValue(row.balancesByBucket, 'taxable'),
        governmental_457b: bucketMapValue(
          row.balancesByBucket,
          'governmental_457b',
        ),
        pre_tax: bucketMapValue(row.balancesByBucket, 'pre_tax'),
        hsa: bucketMapValue(row.balancesByBucket, 'hsa'),
        roth: bucketMapValue(row.balancesByBucket, 'roth'),
        bridge: bucketMapValue(row.balancesByBucket, 'bridge'),
        other: bucketMapValue(row.balancesByBucket, 'other'),
      })),
    [preview?.drawdownSchedule],
  )

  const failureAgeData = useMemo(() => {
    const entries = Object.entries(preview?.failureAgeDistribution ?? {})
    const totalFailures = entries.reduce((sum, [, count]) => sum + count, 0)
    if (totalFailures === 0) return []
    // Counts are per failed trial; rescale so bars read as % of all trials.
    const failedShare = 1 - (preview?.successProbability ?? 1)
    return entries
      .map(([age, count]) => ({
        age: Number(age),
        share: (count / totalFailures) * failedShare * 100,
      }))
      .sort((a, b) => a.age - b.age)
  }, [preview?.failureAgeDistribution, preview?.successProbability])

  const withdrawalData = useMemo(
    () =>
      (preview?.drawdownSchedule ?? [])
        .filter(
          (row) =>
            row.partialRetirementYear || row.primaryAge >= fullRetirementAge,
        )
        .slice(0, 30)
        .map((row) => ({
          age: row.primaryAge,
          cash: bucketMapValue(row.withdrawalsByBucket, 'cash'),
          taxable: bucketMapValue(row.withdrawalsByBucket, 'taxable'),
          governmental_457b: bucketMapValue(
            row.withdrawalsByBucket,
            'governmental_457b',
          ),
          pre_tax: bucketMapValue(row.withdrawalsByBucket, 'pre_tax'),
          hsa: bucketMapValue(row.withdrawalsByBucket, 'hsa'),
          roth: bucketMapValue(row.withdrawalsByBucket, 'roth'),
          other: bucketMapValue(row.withdrawalsByBucket, 'other'),
        })),
    [preview, fullRetirementAge],
  )

  const drawdownRows = useMemo(
    () =>
      (preview?.drawdownSchedule ?? []).filter(
        (row) =>
          row.partialRetirementYear || row.primaryAge >= fullRetirementAge,
      ),
    [preview, fullRetirementAge],
  )

  // Drawdown table rows in the chosen dollar basis. Backend rows are nominal
  // except the engine-decision block (real); the deterministic schedule uses a
  // constant inflation rate, so (1+i)^yearIndex converts exactly both ways.
  // Spend is the spending actually funded (income + bridge + net withdrawal,
  // minus portfolio-paid college) — the engine's target can exceed it in
  // capacity-trimmed years, and RMD-forced surplus is reinvested, not spent.
  const drawdownTableRows = useMemo(() => {
    const inflation = preview?.inputs.inflationRate ?? 0
    return drawdownRows.map((row) => {
      const factor = (1 + inflation) ** row.yearIndex
      const scale = drawdownBasis === 'real' ? 1 / factor : 1
      const bridgeNominal = row.bridgeDraw * factor
      const collegeNominal =
        Math.max(0, row.collegeCost - row.college529Draw) * factor
      // Partial years: the engine never ran, so spendingNeed (already
      // nominal) is the window spend target and spouse take-home joins
      // income in the funding math.
      const targetNominal = row.partialRetirementYear
        ? row.spendingNeed
        : row.spendingTarget * factor
      const incomeNominal = row.income + (row.spouseNetIncome ?? 0)
      const spendNominal = Math.min(
        targetNominal,
        Math.max(
          0,
          incomeNominal + bridgeNominal + row.netWithdrawal - collegeNominal,
        ),
      )
      // ACA/Medicare row fields are real dollars; scale like bridgeDraw.
      const healthcareNominal =
        ((row.acaNet ?? 0) + (row.medicarePremium ?? 0)) * factor
      return {
        ...row,
        displaySpend: spendNominal * scale,
        displayTarget: targetNominal * scale,
        spendTrimmed: targetNominal - spendNominal > 1,
        displayIncome: incomeNominal * scale,
        displaySpouseNet: (row.spouseNetIncome ?? 0) * scale,
        displayBridge: bridgeNominal * scale,
        displayCollege: collegeNominal * scale,
        displayGross: row.grossWithdrawal * scale,
        displayTax: row.taxEstimate * scale,
        displayPenalty: row.penaltyEstimate * scale,
        displayEnding: row.endingBalance * scale,
        displayRmd: row.rmdAmount * scale,
        displayHealthcare: healthcareNominal * scale,
        displayAcaGross: (row.acaPremiumGross ?? 0) * factor * scale,
        // The used credit caps at the chosen plan's premium (net floors
        // at $0 — e.g. Bronze), so gross − subsidy + OOP ties to the cell.
        displayAcaSubsidy:
          Math.min(row.acaSubsidy ?? 0, row.acaPremiumGross ?? 0) *
          factor *
          scale,
        displayAcaOop: (row.acaOop ?? 0) * factor * scale,
        displayMedicare: (row.medicarePremium ?? 0) * factor * scale,
        displayMagi: (row.magi ?? 0) * factor * scale,
        // ACA share of any spend trim: the MAGI true-up repriced the
        // subsidy above what the planning floor budgeted.
        displayAcaReprice:
          Math.max(0, (row.acaNet ?? 0) - (row.acaPlanningNet ?? 0)) *
          factor *
          scale,
        displayBuckets: Object.fromEntries(
          Object.entries(row.withdrawalsByBucket).map(([key, value]) => [
            key,
            value * scale,
          ]),
        ),
      }
    })
  }, [drawdownRows, drawdownBasis, preview?.inputs.inflationRate])
  const drawdownHasBridge = drawdownTableRows.some(
    (row) => row.displayBridge > 0.5,
  )
  const drawdownHasCollege = drawdownTableRows.some(
    (row) => row.displayCollege > 0.5,
  )
  const drawdownHasHealthcare = drawdownTableRows.some(
    (row) => row.displayHealthcare > 0.5,
  )
  const drawdownHasAca = drawdownTableRows.some(
    (row) => (row.acaPremiumGross ?? 0) > 0.5,
  )
  const drawdownColumnCount =
    13 +
    (drawdownHasBridge ? 1 : 0) +
    (drawdownHasCollege ? 1 : 0) +
    (drawdownHasHealthcare ? 1 : 0) +
    (drawdownHasAca ? 1 : 0)

  const gainRatioSource = taxAssumptionText(
    preview?.taxAssumptions,
    'taxableWithdrawalGainRatioSource',
  )
  const gainRatioDetail = taxAssumptionText(
    preview?.taxAssumptions,
    'taxableWithdrawalGainRatioDetail',
  )
  const accountRules: RetirementAccountRule[] = preview?.accountRules ?? []

  return (
    <>
      {previewError ? (
        <LoadErrorState
          title="Failed to run retirement preview."
          detail={
            previewError instanceof Error
              ? previewError.message
              : 'Retry the planner after checking the saved Money assumptions.'
          }
          onRetry={() => onRetry()}
          isRetrying={isFetching}
        />
      ) : null}

      {hasPendingChanges && preview ? (
        <div
          role="status"
          className="rounded-2xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-text-muted"
        >
          Inputs changed since this plan ran — the results below reflect the
          last preview. Click{' '}
          <span className="font-medium text-text">Run preview</span> to refresh.
        </div>
      ) : null}

      {isFetching && preview ? (
        <div
          role="status"
          className="rounded-2xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-text-muted"
        >
          Updating projection…
        </div>
      ) : null}

      <div className="grid gap-6">
        <SectionCard
          variant="surface"
          title="Probability bands"
          description="Portfolio range by age. Wider bands mean return sequence risk matters more."
        >
          <div className="h-72">
            <ResponsiveContainer
              width="100%"
              height="100%"
              minWidth={240}
              minHeight={260}
              initialDimension={{ width: 720, height: 280 }}
            >
              <AreaChart data={projectionData} margin={{ left: 8, right: 8 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                />
                <XAxis dataKey="age" tickLine={false} />
                <YAxis
                  tickFormatter={(value) =>
                    `$${Math.round(Number(value) / 1000)}k`
                  }
                />
                <Tooltip formatter={currencyTooltip} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="p90"
                  name="P90"
                  stroke="var(--color-chart-3)"
                  fill="var(--color-chart-3)"
                  fillOpacity={0.12}
                />
                <Area
                  type="monotone"
                  dataKey="p50"
                  name="P50"
                  stroke="var(--color-chart-1)"
                  fill="var(--color-chart-1)"
                  fillOpacity={0.16}
                />
                <Line
                  type="monotone"
                  dataKey="p10"
                  name="P10"
                  stroke="var(--color-warning)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        {failureAgeData.length > 0 ? (
          <SectionCard
            variant="surface"
            title="When plans fall short"
            description="Share of Monte Carlo trials that first miss the essential floor at each age. Early bars signal sequence-of-returns risk; late bars signal longevity risk."
          >
            <div className="h-56">
              <ResponsiveContainer
                width="100%"
                height="100%"
                minWidth={240}
                minHeight={200}
                initialDimension={{ width: 720, height: 220 }}
              >
                <BarChart data={failureAgeData} margin={{ left: 8, right: 8 }}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--color-border)"
                  />
                  <XAxis dataKey="age" tickLine={false} />
                  <YAxis
                    tickFormatter={(value) => `${Number(value).toFixed(1)}%`}
                  />
                  <Tooltip
                    formatter={(value) => [
                      `${Number(value ?? 0).toFixed(2)}% of trials`,
                      'First shortfall',
                    ]}
                    labelFormatter={(label) => `Age ${label}`}
                  />
                  <Bar dataKey="share" fill="var(--color-warning)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>
        ) : null}

        {preview?.outcomeFraming ? (
          <SectionCard
            variant="surface"
            title="Beyond the success number"
            description="What failure actually means in this model, how much warning it gives, and what the success odds already assume."
            contentClassName="grid gap-3 md:grid-cols-2"
          >
            {preview.outcomeFraming.medianYearsShort != null ? (
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  How plans fail
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {formatCurrencyWhole(
                    preview.outcomeFraming.medianFloorGapReal,
                  )}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  A trial counts as failed after a single year missing the
                  essential floor — discretionary is already cut to zero by
                  then. The median failing trial misses the floor in{' '}
                  {preview.outcomeFraming.medianYearsShort} year
                  {preview.outcomeFraming.medianYearsShort === 1 ? '' : 's'} for
                  this total (today's dollars); the worst decile of failures
                  misses{' '}
                  {formatCurrencyWhole(preview.outcomeFraming.tailFloorGapReal)}
                  .
                </p>
              </div>
            ) : (
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  How plans fail
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  No floor misses
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  No simulated trial misses the essential floor at this knob
                  set.
                </p>
              </div>
            )}
            {preview.outcomeFraming.medianWarningYears != null ? (
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Warning time
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {preview.outcomeFraming.medianWarningYears} year
                  {preview.outcomeFraming.medianWarningYears === 1 ? '' : 's'}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  Median gap between discretionary spending first trimming to
                  zero and the first floor miss. The model never adjusts — a
                  real household has this long to cut spending, downsize, or
                  return to work before the floor breaks.
                </p>
              </div>
            ) : null}
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                Penalty backstop
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {percentPoints(preview.outcomeFraming.penaltyTrialsShare)} of
                trials
              </p>
              <p className="mt-1 text-xs text-text-muted">
                The success odds already assume tapping pre-tax accounts before
                59½ (10% penalty; HSA 20% before 65) when the bridge runs dry.
                {preview.outcomeFraming.medianPenaltyPaidReal != null
                  ? ` Median lifetime penalty cost among those trials: ${formatCurrencyWhole(preview.outcomeFraming.medianPenaltyPaidReal)} (today's dollars).`
                  : ' No trial pays an early-access penalty at this knob set.'}
              </p>
            </div>
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                The other side
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {percentPoints(preview.outcomeFraming.endAboveStartShare)} of
                trials
              </p>
              <p className="mt-1 text-xs text-text-muted">
                End the horizon with at least today's{' '}
                {formatCurrencyWhole(preview.outcomeFraming.startBalanceReal)}{' '}
                still in the accounts (real dollars). Padding the plan further
                trades certain working years for percentage points — weigh it
                against the Sensitivity checks above.
              </p>
            </div>
          </SectionCard>
        ) : null}

        <SectionCard
          variant="surface"
          title="Annual drawdown by source"
          description="Gross withdrawals needed by account type after retirement income sources. Future (inflated) dollars."
        >
          <div className="h-72">
            <ResponsiveContainer
              width="100%"
              height="100%"
              minWidth={240}
              minHeight={260}
              initialDimension={{ width: 720, height: 280 }}
            >
              <BarChart data={withdrawalData} margin={{ left: 8, right: 8 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                />
                <XAxis dataKey="age" tickLine={false} />
                <YAxis
                  tickFormatter={(value) =>
                    `$${Math.round(Number(value) / 1000)}k`
                  }
                />
                <Tooltip formatter={currencyTooltip} />
                <Legend />
                {bucketOrder
                  .filter((bucket) => bucket !== 'bridge')
                  .map((bucket) => (
                    <Bar
                      key={bucket}
                      dataKey={bucket}
                      stackId="withdrawals"
                      name={bucketLabel(bucket)}
                      fill={bucketColors[bucket]}
                    />
                  ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard
          variant="surface"
          title="Account balances by age"
          description="Stacked expected-path balances after contributions, withdrawals, tax estimates, and RMD estimates. Future (inflated) dollars."
        >
          <div className="h-72">
            <ResponsiveContainer
              width="100%"
              height="100%"
              minWidth={240}
              minHeight={260}
              initialDimension={{ width: 720, height: 280 }}
            >
              <AreaChart data={balanceData} margin={{ left: 8, right: 8 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                />
                <XAxis dataKey="age" tickLine={false} />
                <YAxis
                  tickFormatter={(value) =>
                    `$${Math.round(Number(value) / 1000)}k`
                  }
                />
                <Tooltip formatter={currencyTooltip} />
                <Legend />
                {bucketOrder.map((bucket) => (
                  <Area
                    key={bucket}
                    type="monotone"
                    dataKey={bucket}
                    stackId="1"
                    name={bucketLabel(bucket)}
                    stroke={bucketColors[bucket]}
                    fill={bucketColors[bucket]}
                    fillOpacity={0.55}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>

      <SectionCard
        variant="surface"
        title="Drawdown schedule"
        description={`Year-by-year funded spending, income, taxes, early-withdrawal penalties, and withdrawal source mix in ${
          drawdownBasis === 'real'
            ? "today's dollars"
            : 'future (inflated) dollars'
        }.`}
      >
        <div className="mb-3 flex flex-wrap gap-2">
          {(
            [
              ['real', "Today's dollars"],
              ['nominal', 'Future dollars'],
            ] as const
          ).map(([value, label]) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={drawdownBasis === value ? 'default' : 'outline'}
              onClick={() => setDrawdownBasis(value)}
            >
              {label}
            </Button>
          ))}
        </div>
        <div className="overflow-hidden rounded-2xl border border-border/35 bg-surface-muted/10">
          <div className="overflow-auto">
            <table className="w-full min-w-[1080px] border-separate border-spacing-0 text-sm">
              <thead className="bg-bg/95 backdrop-blur">
                <tr>
                  {[
                    { label: 'Age' },
                    {
                      label: 'Spend',
                      title:
                        'Retirement spending actually funded this year (income + bridge + net withdrawal). Shown in amber when the withdrawal strategy trims it below the plan target.',
                    },
                    { label: 'Income' },
                    ...(drawdownHasBridge
                      ? [
                          {
                            label: 'Bridge',
                            title:
                              'Spending covered by the bridge sleeve carved out at retirement. Not part of Withdrawal.',
                          },
                        ]
                      : []),
                    { label: 'Withdrawal' },
                    { label: 'Tax est.', title: taxEstimateTooltip },
                    { label: 'Penalty' },
                    ...(drawdownHasCollege
                      ? [
                          {
                            label: 'College',
                            title:
                              'College costs paid from the portfolio after the 529 sleeve runs out. Included in Withdrawal; 529-funded amounts never touch retirement accounts.',
                          },
                        ]
                      : []),
                    ...(drawdownHasHealthcare
                      ? [
                          {
                            label: 'Healthcare',
                            title:
                              'ACA premium net of the premium tax credit, plus out-of-pocket, plus Medicare from 65. Already part of Spend — it rides the essential floor, so withdrawals are sized to cover it.',
                          },
                        ]
                      : []),
                    ...(drawdownHasAca
                      ? [
                          {
                            label: 'MAGI',
                            title:
                              "Modeled MAGI that priced the ACA subsidy: ordinary income + full Social Security + pre-tax/457(b)/HSA draws + the taxable draw's gain share. The credit ends above 400% of the federal poverty line — amber marks cliff years.",
                          },
                        ]
                      : []),
                    { label: 'Cash' },
                    { label: 'Taxable' },
                    { label: 'Gov 457(b)' },
                    { label: 'Pre-tax' },
                    { label: 'Roth' },
                    { label: 'Ending' },
                    { label: 'RMD' },
                  ].map((heading) => (
                    <th
                      key={heading.label}
                      className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted first:text-left"
                      title={heading.title}
                    >
                      {heading.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {drawdownTableRows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={drawdownColumnCount}
                      className="px-4 py-10 text-center text-sm text-text-muted"
                    >
                      Drawdown rows will appear after the preview runs.
                    </td>
                  </tr>
                ) : (
                  drawdownTableRows.map((row) => (
                    <tr key={`${row.calendarYear}-${row.primaryAge}`}>
                      <td className="border-b border-border/20 px-4 py-3 text-left font-medium text-text">
                        {row.primaryAge}
                        {row.partialRetirementYear ? (
                          <Badge
                            variant="secondary"
                            className="ml-2"
                            title="Partial retirement: you are retired, spouse still working — the spend gap above their take-home is drawn from the portfolio."
                          >
                            Partial
                          </Badge>
                        ) : null}
                      </td>
                      <td
                        className={`border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums ${
                          row.spendTrimmed ? 'text-warning' : 'text-text'
                        }`}
                        title={
                          row.spendTrimmed
                            ? [
                                `Below the ${formatCurrency(row.displayTarget, {
                                  decimals: 0,
                                })} target — the withdrawal strategy trimmed discretionary spending this year.`,
                                row.displayAcaReprice > 1
                                  ? `${formatCurrency(row.displayAcaReprice, { decimals: 0 })} of the gap is ACA repricing: the MAGI true-up cut the subsidy below plan.`
                                  : '',
                              ]
                                .filter(Boolean)
                                .join(' ')
                            : undefined
                        }
                      >
                        {formatCurrency(row.displaySpend, { decimals: 0 })}
                      </td>
                      <td
                        className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text"
                        title={
                          row.partialRetirementYear
                            ? `Includes spouse take-home ${formatCurrency(row.displaySpouseNet, { decimals: 0 })}.`
                            : undefined
                        }
                      >
                        {formatCurrency(row.displayIncome, { decimals: 0 })}
                      </td>
                      {drawdownHasBridge ? (
                        <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                          {formatCurrency(row.displayBridge, { decimals: 0 })}
                        </td>
                      ) : null}
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayGross, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-warning">
                        {formatCurrency(row.displayTax, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-warning">
                        {formatCurrency(row.displayPenalty, { decimals: 0 })}
                      </td>
                      {drawdownHasCollege ? (
                        <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                          {formatCurrency(row.displayCollege, { decimals: 0 })}
                        </td>
                      ) : null}
                      {drawdownHasHealthcare ? (
                        <td
                          className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text"
                          title={[
                            `ACA gross ${formatCurrency(row.displayAcaGross, { decimals: 0 })} − subsidy ${formatCurrency(row.displayAcaSubsidy, { decimals: 0 })} + out-of-pocket ${formatCurrency(row.displayAcaOop, { decimals: 0 })} + Medicare ${formatCurrency(row.displayMedicare, { decimals: 0 })}.`,
                            row.displayAcaReprice > 1
                              ? `Includes ${formatCurrency(row.displayAcaReprice, { decimals: 0 })} above plan — the MAGI true-up repriced the subsidy.`
                              : '',
                          ]
                            .filter(Boolean)
                            .join(' ')}
                        >
                          {formatCurrency(row.displayHealthcare, {
                            decimals: 0,
                          })}
                        </td>
                      ) : null}
                      {drawdownHasAca ? (
                        <td
                          className={`border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums ${
                            row.acaPremiumGross > 0.5 && row.acaSubsidy < 0.5
                              ? 'text-warning'
                              : 'text-text-muted'
                          }`}
                          title={
                            row.acaPremiumGross > 0.5 && row.acaSubsidy < 0.5
                              ? 'Above the 400% FPL cliff — no premium tax credit this year.'
                              : undefined
                          }
                        >
                          {row.acaPremiumGross > 0.5
                            ? formatCurrency(row.displayMagi, { decimals: 0 })
                            : '—'}
                        </td>
                      ) : null}
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayBuckets.cash ?? 0, {
                          decimals: 0,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayBuckets.taxable ?? 0, {
                          decimals: 0,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(
                          bucketMapValue(
                            row.displayBuckets,
                            'governmental_457b',
                          ),
                          { decimals: 0 },
                        )}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(
                          bucketMapValue(row.displayBuckets, 'pre_tax'),
                          { decimals: 0 },
                        )}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayBuckets.roth ?? 0, {
                          decimals: 0,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayEnding, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right">
                        {row.rmdApplied ? (
                          <Badge variant="warning">
                            {formatCurrency(row.displayRmd, { decimals: 0 })}
                          </Badge>
                        ) : (
                          <span className="text-text-muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
        {drawdownTableRows.length > 0 ? (
          <p className="mt-3 text-xs text-text-muted">
            Each year reconciles: Spend = Income{' '}
            {drawdownHasBridge ? '+ Bridge ' : ''}+ Withdrawal − Tax est. −
            Penalty{drawdownHasCollege ? ' − College' : ''}. When a forced RMD
            withdraws more than the plan needs, the surplus is reinvested in
            taxable rather than spent.
            {drawdownHasHealthcare
              ? ' Healthcare is not subtracted — it rides the essential floor inside Spend, so withdrawals are sized to cover it. Amber-trimmed years can include ACA repricing: when draws push MAGI across a subsidy band, the true-up adds the lost credit to that year’s need.'
              : ''}
          </p>
        ) : null}
        {gainRatioDetail ? (
          <p className="mt-3 text-xs text-text-muted">
            <span
              className={`mr-2 inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                gainRatioSource === 'tax_lots'
                  ? freshnessToneClass('fresh')
                  : freshnessToneClass('needs_evidence')
              }`}
            >
              {gainRatioSource === 'tax_lots'
                ? 'From your cost basis'
                : 'Planning assumption'}
            </span>
            {gainRatioDetail}
          </p>
        ) : null}
      </SectionCard>

      {accountRules.length > 0 ? (
        <SectionCard
          variant="surface"
          title="How each account is treated"
          description="What the planner assumes for early access and required distributions per account type. Planning context, not tax advice."
        >
          <div className="grid gap-3 md:grid-cols-2">
            {accountRules.map((rule) => (
              <div
                key={rule.bucketType}
                className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text">
                    {rule.label}
                  </p>
                  <Badge variant="outline">{rule.taxTreatment}</Badge>
                </div>
                <p className="mt-2 text-xs text-text-muted">
                  <span className="font-medium text-text">Early access:</span>{' '}
                  {rule.earlyAccess}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  <span className="font-medium text-text">RMDs:</span>{' '}
                  {rule.rmd}
                </p>
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}
    </>
  )
}
