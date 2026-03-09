'use client'

import { useEffect, useState } from 'react'
import type { HouseholdProfile } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useUpdateHouseholdProfile } from '@/lib/hooks/useHousehold'
import { formatCurrency } from './formatters'

function numberInput(value: number | null): string {
  return value == null ? '' : String(value)
}

function parseNullableNumber(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

export function HouseholdProfileCard({ profile }: { profile: HouseholdProfile }) {
  const updateProfile = useUpdateHouseholdProfile()
  const [householdName, setHouseholdName] = useState(profile.householdName)
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
  const [notes, setNotes] = useState(profile.notes ?? '')

  useEffect(() => {
    setHouseholdName(profile.householdName)
    setMonthlyNetIncomeTarget(numberInput(profile.monthlyNetIncomeTarget))
    setMonthlyEssentialTarget(numberInput(profile.monthlyEssentialTarget))
    setMonthlyDiscretionaryTarget(numberInput(profile.monthlyDiscretionaryTarget))
    setMonthlySavingsTarget(numberInput(profile.monthlySavingsTarget))
    setTargetRetirementAge(numberInput(profile.targetRetirementAge))
    setTargetRetirementSpend(numberInput(profile.targetRetirementSpend))
    setNotes(profile.notes ?? '')
  }, [profile])

  const handleSubmit = () => {
    updateProfile.mutate({
      householdName: householdName.trim(),
      monthlyNetIncomeTarget: parseNullableNumber(monthlyNetIncomeTarget),
      monthlyEssentialTarget: parseNullableNumber(monthlyEssentialTarget),
      monthlyDiscretionaryTarget: parseNullableNumber(monthlyDiscretionaryTarget),
      monthlySavingsTarget: parseNullableNumber(monthlySavingsTarget),
      targetRetirementAge: parseNullableNumber(targetRetirementAge),
      targetRetirementSpend: parseNullableNumber(targetRetirementSpend),
      notes: notes.trim() || null,
    })
  }

  return (
    <SectionCard
      variant="surface"
      title="Household Plan"
      description="Set the assumptions Jenny needs before she starts policing budget drift and retirement readiness."
      actions={
        <Button onClick={handleSubmit} disabled={updateProfile.isPending}>
          {updateProfile.isPending ? 'Saving...' : 'Save Plan'}
        </Button>
      }
    >
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
            <Label htmlFor="monthly-income">Monthly take-home income</Label>
            <Input
              id="monthly-income"
              inputMode="decimal"
              value={monthlyNetIncomeTarget}
              onChange={(event) => setMonthlyNetIncomeTarget(event.target.value)}
              placeholder="12500"
            />
          </div>
          <div>
            <Label htmlFor="monthly-essential">Essential budget</Label>
            <Input
              id="monthly-essential"
              inputMode="decimal"
              value={monthlyEssentialTarget}
              onChange={(event) => setMonthlyEssentialTarget(event.target.value)}
              placeholder="5200"
            />
          </div>
          <div>
            <Label htmlFor="monthly-discretionary">Discretionary budget</Label>
            <Input
              id="monthly-discretionary"
              inputMode="decimal"
              value={monthlyDiscretionaryTarget}
              onChange={(event) => setMonthlyDiscretionaryTarget(event.target.value)}
              placeholder="1800"
            />
          </div>
          <div>
            <Label htmlFor="monthly-savings">Monthly savings target</Label>
            <Input
              id="monthly-savings"
              inputMode="decimal"
              value={monthlySavingsTarget}
              onChange={(event) => setMonthlySavingsTarget(event.target.value)}
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
            <Label htmlFor="retirement-spend">Target monthly retirement spend</Label>
            <Input
              id="retirement-spend"
              inputMode="decimal"
              value={targetRetirementSpend}
              onChange={(event) => setTargetRetirementSpend(event.target.value)}
              placeholder="9000"
            />
          </div>
        </div>

        <div className="rounded-2xl border border-border/50 bg-surface-muted/30 p-5">
          <p className="text-sm font-semibold text-text">Current targets</p>
          <div className="mt-4 space-y-3 text-sm text-text-muted">
            <p>Income: {formatCurrency(parseNullableNumber(monthlyNetIncomeTarget))}</p>
            <p>Essentials: {formatCurrency(parseNullableNumber(monthlyEssentialTarget))}</p>
            <p>
              Flexible spend: {formatCurrency(parseNullableNumber(monthlyDiscretionaryTarget))}
            </p>
            <p>Savings: {formatCurrency(parseNullableNumber(monthlySavingsTarget))}</p>
            <p>
              Retirement: age {parseNullableNumber(targetRetirementAge) ?? 'Not set'} /{' '}
              {formatCurrency(parseNullableNumber(targetRetirementSpend))}
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
    </SectionCard>
  )
}
