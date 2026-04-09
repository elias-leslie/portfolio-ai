'use client'

import { useEffect, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type {
  HouseholdProfile,
  HouseholdResolvedValue,
} from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { useUpdateHouseholdProfile } from '@/lib/hooks/useHousehold'
import {
  formatResolvedValue,
  numberInput,
  parseNullableNumber,
} from './household-profile-utils'

function badgeVariantForStatus(status: string) {
  switch (status) {
    case 'confirmed':
      return 'success' as const
    case 'inferred':
      return 'warning' as const
    case 'missing':
      return 'outline' as const
    default:
      return 'secondary' as const
  }
}

export function HouseholdProfileCard({
  profile,
  resolvedValues,
}: {
  profile: HouseholdProfile
  resolvedValues: HouseholdResolvedValue[]
}) {
  const updateProfile = useUpdateHouseholdProfile()
  const [householdName, setHouseholdName] = useState(profile.householdName)
  const [adultCount, setAdultCount] = useState(
    numberInput(profile.adultCount ?? null),
  )
  const [dependentCount, setDependentCount] = useState(
    numberInput(profile.dependentCount ?? null),
  )
  const [monthlyNetIncomeTarget, setMonthlyNetIncomeTarget] = useState(
    numberInput(profile.monthlyNetIncomeTarget),
  )
  const [monthlyEssentialTarget, setMonthlyEssentialTarget] = useState(
    numberInput(profile.monthlyEssentialTarget),
  )
  const [monthlyDiscretionaryTarget, setMonthlyDiscretionaryTarget] = useState(
    numberInput(profile.monthlyDiscretionaryTarget),
  )
  const [monthlySavingsTarget, setMonthlySavingsTarget] = useState(
    numberInput(profile.monthlySavingsTarget),
  )
  const [targetRetirementAge, setTargetRetirementAge] = useState(
    numberInput(profile.targetRetirementAge),
  )
  const [targetRetirementSpend, setTargetRetirementSpend] = useState(
    numberInput(profile.targetRetirementSpend),
  )
  const [filingStatus, setFilingStatus] = useState(profile.filingStatus ?? '')
  const [stateOfResidence, setStateOfResidence] = useState(
    profile.stateOfResidence ?? '',
  )
  const [effectiveTaxRate, setEffectiveTaxRate] = useState(
    numberInput(profile.effectiveTaxRate ?? null),
  )
  const [marginalFederalTaxRate, setMarginalFederalTaxRate] = useState(
    numberInput(profile.marginalFederalTaxRate ?? null),
  )
  const [marginalStateTaxRate, setMarginalStateTaxRate] = useState(
    numberInput(profile.marginalStateTaxRate ?? null),
  )
  const [emergencyFundTargetMonths, setEmergencyFundTargetMonths] = useState(
    numberInput(profile.emergencyFundTargetMonths ?? null),
  )
  const [emergencyFundTargetAmount, setEmergencyFundTargetAmount] = useState(
    numberInput(profile.emergencyFundTargetAmount ?? null),
  )
  const [notes, setNotes] = useState(profile.notes ?? '')

  useEffect(() => {
    setHouseholdName(profile.householdName)
    setAdultCount(numberInput(profile.adultCount ?? null))
    setDependentCount(numberInput(profile.dependentCount ?? null))
    setMonthlyNetIncomeTarget(numberInput(profile.monthlyNetIncomeTarget))
    setMonthlyEssentialTarget(numberInput(profile.monthlyEssentialTarget))
    setMonthlyDiscretionaryTarget(
      numberInput(profile.monthlyDiscretionaryTarget),
    )
    setMonthlySavingsTarget(numberInput(profile.monthlySavingsTarget))
    setTargetRetirementAge(numberInput(profile.targetRetirementAge))
    setTargetRetirementSpend(numberInput(profile.targetRetirementSpend))
    setFilingStatus(profile.filingStatus ?? '')
    setStateOfResidence(profile.stateOfResidence ?? '')
    setEffectiveTaxRate(numberInput(profile.effectiveTaxRate ?? null))
    setMarginalFederalTaxRate(
      numberInput(profile.marginalFederalTaxRate ?? null),
    )
    setMarginalStateTaxRate(numberInput(profile.marginalStateTaxRate ?? null))
    setEmergencyFundTargetMonths(
      numberInput(profile.emergencyFundTargetMonths ?? null),
    )
    setEmergencyFundTargetAmount(
      numberInput(profile.emergencyFundTargetAmount ?? null),
    )
    setNotes(profile.notes ?? '')
  }, [profile])

  const handleSubmit = () => {
    updateProfile.mutate({
      householdName: householdName.trim(),
      adultCount: parseNullableNumber(adultCount),
      dependentCount: parseNullableNumber(dependentCount),
      monthlyNetIncomeTarget: parseNullableNumber(monthlyNetIncomeTarget),
      monthlyEssentialTarget: parseNullableNumber(monthlyEssentialTarget),
      monthlyDiscretionaryTarget: parseNullableNumber(
        monthlyDiscretionaryTarget,
      ),
      monthlySavingsTarget: parseNullableNumber(monthlySavingsTarget),
      targetRetirementAge: parseNullableNumber(targetRetirementAge),
      targetRetirementSpend: parseNullableNumber(targetRetirementSpend),
      filingStatus: filingStatus.trim() || null,
      stateOfResidence: stateOfResidence.trim() || null,
      effectiveTaxRate: parseNullableNumber(effectiveTaxRate),
      marginalFederalTaxRate: parseNullableNumber(marginalFederalTaxRate),
      marginalStateTaxRate: parseNullableNumber(marginalStateTaxRate),
      emergencyFundTargetMonths: parseNullableNumber(emergencyFundTargetMonths),
      emergencyFundTargetAmount: parseNullableNumber(emergencyFundTargetAmount),
      notes: notes.trim() || null,
    })
  }

  return (
    <SectionCard
      variant="surface"
      title="Jenny Household Plan"
      description="Jenny should infer most of this from your documents. Use manual overrides only when you want to steer or confirm the plan directly."
      actions={
        <Button
          onClick={handleSubmit}
          disabled={updateProfile.isPending}
          aria-busy={updateProfile.isPending}
        >
          {updateProfile.isPending ? 'Saving...' : 'Save Overrides'}
        </Button>
      }
    >
      <div className="space-y-6">
        <div className="grid gap-4 xl:grid-cols-3">
          {resolvedValues.length === 0 ? (
            <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4 text-sm text-text-muted xl:col-span-3">
              Jenny has not resolved any structured planning values yet. Upload
              documents or set an override to start building the household plan.
            </div>
          ) : (
            resolvedValues.map((value) => (
              <div
                key={value.fieldName}
                className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">
                      {value.label}
                    </p>
                    <p className="mt-2 text-base font-semibold text-text">
                      {formatResolvedValue(value)}
                    </p>
                  </div>
                  <Badge variant={badgeVariantForStatus(value.status)}>
                    {formatEnumLabel(value.status)}
                  </Badge>
                </div>
                <div className="mt-3 space-y-2 text-sm text-text-muted">
                  <p>
                    Source:{' '}
                    {value.source === 'jenny_inference'
                      ? 'Jenny estimate'
                      : value.source === 'manual'
                        ? 'Confirmed override'
                        : 'Pending'}
                  </p>
                  {value.confidence != null ? (
                    <p>Confidence: {Math.round(value.confidence * 100)}%</p>
                  ) : null}
                  {value.rationale ? <p>{value.rationale}</p> : null}
                  {value.question ? (
                    <p>Needs confirmation: {value.question}</p>
                  ) : null}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor="household-name">Household name</Label>
              <Input
                id="household-name"
                value={householdName}
                onChange={(event) => setHouseholdName(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="adult-count">Adults in household</Label>
              <Input
                id="adult-count"
                inputMode="numeric"
                value={adultCount}
                onChange={(event) => setAdultCount(event.target.value)}
                placeholder="2"
              />
            </div>
            <div>
              <Label htmlFor="dependent-count">Dependents</Label>
              <Input
                id="dependent-count"
                inputMode="numeric"
                value={dependentCount}
                onChange={(event) => setDependentCount(event.target.value)}
                placeholder="2"
              />
            </div>
            <div>
              <Label htmlFor="monthly-income">Monthly take-home income</Label>
              <Input
                id="monthly-income"
                inputMode="decimal"
                value={monthlyNetIncomeTarget}
                onChange={(event) =>
                  setMonthlyNetIncomeTarget(event.target.value)
                }
                placeholder="12500"
              />
            </div>
            <div>
              <Label htmlFor="monthly-essential">Essential budget</Label>
              <Input
                id="monthly-essential"
                inputMode="decimal"
                value={monthlyEssentialTarget}
                onChange={(event) =>
                  setMonthlyEssentialTarget(event.target.value)
                }
                placeholder="5200"
              />
            </div>
            <div>
              <Label htmlFor="monthly-discretionary">
                Discretionary budget
              </Label>
              <Input
                id="monthly-discretionary"
                inputMode="decimal"
                value={monthlyDiscretionaryTarget}
                onChange={(event) =>
                  setMonthlyDiscretionaryTarget(event.target.value)
                }
                placeholder="1800"
              />
            </div>
            <div>
              <Label htmlFor="monthly-savings">Monthly savings target</Label>
              <Input
                id="monthly-savings"
                inputMode="decimal"
                value={monthlySavingsTarget}
                onChange={(event) =>
                  setMonthlySavingsTarget(event.target.value)
                }
                placeholder="2600"
              />
            </div>
            <div>
              <Label htmlFor="retirement-age">Target retirement age</Label>
              <Input
                id="retirement-age"
                inputMode="numeric"
                value={targetRetirementAge}
                onChange={(event) => setTargetRetirementAge(event.target.value)}
                placeholder="60"
              />
            </div>
            <div>
              <Label htmlFor="retirement-spend">
                Target monthly retirement spend
              </Label>
              <Input
                id="retirement-spend"
                inputMode="decimal"
                value={targetRetirementSpend}
                onChange={(event) =>
                  setTargetRetirementSpend(event.target.value)
                }
                placeholder="9000"
              />
            </div>
            <div>
              <Label htmlFor="filing-status">Tax filing status</Label>
              <Input
                id="filing-status"
                value={filingStatus}
                onChange={(event) => setFilingStatus(event.target.value)}
                placeholder="married_filing_jointly"
              />
            </div>
            <div>
              <Label htmlFor="state-of-residence">State of residence</Label>
              <Input
                id="state-of-residence"
                value={stateOfResidence}
                onChange={(event) => setStateOfResidence(event.target.value)}
                placeholder="NC"
              />
            </div>
            <div>
              <Label htmlFor="effective-tax-rate">Effective tax rate (%)</Label>
              <Input
                id="effective-tax-rate"
                inputMode="decimal"
                value={effectiveTaxRate}
                onChange={(event) => setEffectiveTaxRate(event.target.value)}
                placeholder="24"
              />
            </div>
            <div>
              <Label htmlFor="federal-tax-rate">
                Federal marginal tax rate (%)
              </Label>
              <Input
                id="federal-tax-rate"
                inputMode="decimal"
                value={marginalFederalTaxRate}
                onChange={(event) =>
                  setMarginalFederalTaxRate(event.target.value)
                }
                placeholder="22"
              />
            </div>
            <div>
              <Label htmlFor="state-tax-rate">
                State marginal tax rate (%)
              </Label>
              <Input
                id="state-tax-rate"
                inputMode="decimal"
                value={marginalStateTaxRate}
                onChange={(event) =>
                  setMarginalStateTaxRate(event.target.value)
                }
                placeholder="5"
              />
            </div>
            <div>
              <Label htmlFor="emergency-fund-months">
                Emergency fund target (months)
              </Label>
              <Input
                id="emergency-fund-months"
                inputMode="decimal"
                value={emergencyFundTargetMonths}
                onChange={(event) =>
                  setEmergencyFundTargetMonths(event.target.value)
                }
                placeholder="6"
              />
            </div>
            <div>
              <Label htmlFor="emergency-fund-amount">
                Emergency fund target amount
              </Label>
              <Input
                id="emergency-fund-amount"
                inputMode="decimal"
                value={emergencyFundTargetAmount}
                onChange={(event) =>
                  setEmergencyFundTargetAmount(event.target.value)
                }
                placeholder="30000"
              />
            </div>
          </div>

          <div className="rounded-2xl border border-border/50 bg-surface-muted/30 p-5">
            <p className="text-sm font-semibold text-text">Manual overrides</p>
            <div className="mt-4 space-y-3 text-sm text-text-muted">
              <p>
                Household: {parseNullableNumber(adultCount) ?? '—'} adult(s),{' '}
                {parseNullableNumber(dependentCount) ?? '—'} dependent(s)
              </p>
              <p>
                Income:{' '}
                {formatCurrency(parseNullableNumber(monthlyNetIncomeTarget), {
                  decimals: 0,
                  nullDisplay: 'Not set',
                })}
              </p>
              <p>
                Essentials:{' '}
                {formatCurrency(parseNullableNumber(monthlyEssentialTarget), {
                  decimals: 0,
                  nullDisplay: 'Not set',
                })}
              </p>
              <p>
                Flexible spend:{' '}
                {formatCurrency(
                  parseNullableNumber(monthlyDiscretionaryTarget),
                  { decimals: 0, nullDisplay: 'Not set' },
                )}
              </p>
              <p>
                Savings:{' '}
                {formatCurrency(parseNullableNumber(monthlySavingsTarget), {
                  decimals: 0,
                  nullDisplay: 'Not set',
                })}
              </p>
              <p>
                Retirement: age{' '}
                {parseNullableNumber(targetRetirementAge) ?? 'Not set'} /{' '}
                {formatCurrency(parseNullableNumber(targetRetirementSpend), {
                  decimals: 0,
                  nullDisplay: 'Not set',
                })}
              </p>
              <p>
                Taxes: {filingStatus || 'Not set'} in {stateOfResidence || '—'}
              </p>
              <p>
                Emergency fund:{' '}
                {parseNullableNumber(emergencyFundTargetMonths) ?? '—'} months /{' '}
                {formatCurrency(
                  parseNullableNumber(emergencyFundTargetAmount),
                  { decimals: 0, nullDisplay: 'Not set' },
                )}
              </p>
            </div>
            <div className="mt-5">
              <Label htmlFor="household-notes">Notes</Label>
              <Textarea
                id="household-notes"
                className="mt-2 min-h-32"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Travel goals, one-time expenses, pension assumptions, healthcare concerns..."
              />
            </div>
          </div>
        </div>
      </div>
    </SectionCard>
  )
}
