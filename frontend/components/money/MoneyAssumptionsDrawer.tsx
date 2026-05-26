'use client'

import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import {
  ASSUMPTION_META_PREFIX,
  assumptionMetaMap,
  cadenceValueFromMonthly,
  type IncomeCadence,
  monthlyValueFromCadence,
  serializeAssumptionMeta,
} from '@/components/money/household-fact-metadata'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type {
  HouseholdConfirmedFact,
  HouseholdProfile,
  HouseholdProfileUpdate,
  HouseholdResolvedValue,
} from '@/lib/api/household'
import { formatCurrency } from '@/lib/formatters'
import {
  useConfirmFact,
  useUpdateHouseholdProfile,
} from '@/lib/hooks/useHousehold'

import { formatResolvedValue } from './household-profile-utils'

type AssumptionFieldType =
  | 'currency'
  | 'integer'
  | 'number'
  | 'percent'
  | 'text'

type AssumptionFieldDef = {
  fieldName: string
  profileKey: keyof HouseholdProfileUpdate & keyof HouseholdProfile
  label: string
  type: AssumptionFieldType
  hint: string
  placeholder?: string
  acceptsFoundValue?: boolean
  supportsCadence?: boolean
  percentStorage?: 'fraction'
}

const assumptionFields: AssumptionFieldDef[] = [
  {
    fieldName: 'adult_count',
    profileKey: 'adultCount',
    label: 'Adults in household',
    type: 'integer',
    hint: 'Core scope for budgets and planning assumptions.',
    placeholder: '2',
  },
  {
    fieldName: 'dependent_count',
    profileKey: 'dependentCount',
    label: 'Dependents',
    type: 'integer',
    hint: 'Used for planning complexity and recurring household needs.',
    placeholder: '0',
  },
  {
    fieldName: 'monthly_net_income_target',
    profileKey: 'monthlyNetIncomeTarget',
    label: 'Take-home income',
    type: 'currency',
    hint: 'The income figure Jenny should budget against.',
    placeholder: '12500',
    supportsCadence: true,
  },
  {
    fieldName: 'monthly_essential_target',
    profileKey: 'monthlyEssentialTarget',
    label: 'Essential budget',
    type: 'currency',
    hint: 'Housing, food, utilities, insurance, debt minimums.',
    placeholder: '5200',
  },
  {
    fieldName: 'monthly_discretionary_target',
    profileKey: 'monthlyDiscretionaryTarget',
    label: 'Discretionary budget',
    type: 'currency',
    hint: 'Optional spending Jenny should treat as the flex lane.',
    placeholder: '1800',
  },
  {
    fieldName: 'monthly_savings_target',
    profileKey: 'monthlySavingsTarget',
    label: 'Savings target',
    type: 'currency',
    hint: 'Monthly amount the household wants left over on purpose.',
    placeholder: '2500',
  },
  {
    fieldName: 'effective_tax_rate',
    profileKey: 'effectiveTaxRate',
    label: 'Effective tax rate',
    type: 'percent',
    hint: 'Useful for translating gross income or planning values into take-home assumptions.',
    placeholder: '24',
  },
  {
    fieldName: 'marginal_federal_tax_rate',
    profileKey: 'marginalFederalTaxRate',
    label: 'Federal marginal tax rate',
    type: 'percent',
    hint: 'Helps Jenny reason about incremental income or retirement tax tradeoffs.',
    placeholder: '22',
  },
  {
    fieldName: 'marginal_state_tax_rate',
    profileKey: 'marginalStateTaxRate',
    label: 'State marginal tax rate',
    type: 'percent',
    hint: 'Used when state tax drag matters for decisions or withdrawals.',
    placeholder: '5',
  },
  {
    fieldName: 'emergency_fund_target_months',
    profileKey: 'emergencyFundTargetMonths',
    label: 'Emergency fund target months',
    type: 'number',
    hint: 'How much runway cash should cover before Jenny calls it fully funded.',
    placeholder: '6',
  },
  {
    fieldName: 'emergency_fund_target_amount',
    profileKey: 'emergencyFundTargetAmount',
    label: 'Emergency fund target amount',
    type: 'currency',
    hint: 'Override the runway target with a hard dollar amount if needed.',
    placeholder: '25000',
  },
  {
    fieldName: 'filing_status',
    profileKey: 'filingStatus',
    label: 'Tax filing status',
    type: 'text',
    hint: 'Use plain language if that is clearer than tax-form wording.',
    placeholder: 'Married filing jointly',
  },
  {
    fieldName: 'state_of_residence',
    profileKey: 'stateOfResidence',
    label: 'State of residence',
    type: 'text',
    hint: 'Only needed if state taxes or benefits meaningfully change decisions.',
    placeholder: 'NC',
  },
  {
    fieldName: 'target_retirement_age',
    profileKey: 'targetRetirementAge',
    label: 'Your retirement age',
    type: 'integer',
    hint: 'The age Jenny should use for preparedness framing.',
    placeholder: '60',
  },
  {
    fieldName: 'target_spouse_retirement_age',
    profileKey: 'targetSpouseRetirementAge',
    label: 'Spouse retirement age',
    type: 'integer',
    hint: 'Spouse work-stop age for retirement preview timing.',
    placeholder: '60',
  },
  {
    fieldName: 'target_retirement_spend',
    profileKey: 'targetRetirementSpend',
    label: 'Retirement monthly spend',
    type: 'currency',
    hint: 'Expected monthly lifestyle cost once work income stops.',
    placeholder: '9000',
  },
  {
    fieldName: 'retirement_inflation_rate',
    profileKey: 'retirementInflationRate',
    label: 'Retirement inflation rate',
    type: 'percent',
    hint: 'Default inflation assumption for retirement previews.',
    placeholder: '2.5',
    percentStorage: 'fraction',
  },
  {
    fieldName: 'retirement_horizon_years',
    profileKey: 'retirementHorizonYears',
    label: 'Retirement horizon years',
    type: 'integer',
    hint: 'How many years the retirement preview should project.',
    placeholder: '35',
  },
  {
    fieldName: 'primary_social_security_annual_earnings',
    profileKey: 'primarySocialSecurityAnnualEarnings',
    label: 'Your Social Security salary',
    type: 'currency',
    hint: 'Annual earnings used for the rough Social Security estimate.',
    placeholder: '120000',
  },
  {
    fieldName: 'primary_social_security_monthly',
    profileKey: 'primarySocialSecurityMonthly',
    label: 'Your Social Security monthly',
    type: 'currency',
    hint: 'Exact monthly SSA estimate, when known.',
    placeholder: '2800',
  },
  {
    fieldName: 'primary_social_security_start_age',
    profileKey: 'primarySocialSecurityStartAge',
    label: 'Your Social Security age',
    type: 'integer',
    hint: 'Age to start Social Security in retirement previews.',
    placeholder: '67',
  },
  {
    fieldName: 'spouse_social_security_annual_earnings',
    profileKey: 'spouseSocialSecurityAnnualEarnings',
    label: 'Spouse Social Security salary',
    type: 'currency',
    hint: 'Annual earnings used for the rough spouse Social Security estimate.',
    placeholder: '90000',
  },
  {
    fieldName: 'spouse_social_security_monthly',
    profileKey: 'spouseSocialSecurityMonthly',
    label: 'Spouse Social Security monthly',
    type: 'currency',
    hint: 'Exact monthly SSA estimate for spouse, when known.',
    placeholder: '2200',
  },
  {
    fieldName: 'spouse_social_security_start_age',
    profileKey: 'spouseSocialSecurityStartAge',
    label: 'Spouse Social Security age',
    type: 'integer',
    hint: 'Spouse age to start Social Security in retirement previews.',
    placeholder: '67',
  },
  {
    fieldName: 'social_security_payable_ratio',
    profileKey: 'socialSecurityPayableRatio',
    label: 'Social Security payable %',
    type: 'percent',
    hint: 'Percent of scheduled SSA benefits to model after projected trust fund depletion.',
    placeholder: '77',
    percentStorage: 'fraction',
  },
]

const cadenceOptions: Array<{ value: IncomeCadence; label: string }> = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'biweekly', label: 'Biweekly' },
  { value: 'annual', label: 'Annual' },
]

function formatCurrentValue(def: AssumptionFieldDef, value: unknown) {
  if (value == null || value === '') {
    return '—'
  }
  if (def.type === 'currency' && typeof value === 'number') {
    return formatCurrency(value, { decimals: 0 })
  }
  if (def.type === 'percent' && typeof value === 'number') {
    const displayValue = def.percentStorage === 'fraction' ? value * 100 : value
    return `${displayValue}%`
  }
  if (def.fieldName === 'target_retirement_age' && typeof value === 'number') {
    return `Age ${value}`
  }
  return String(value)
}

function parseNumericInput(rawValue: string) {
  const normalized = rawValue
    .trim()
    .replace(/[$,%\s]/g, '')
    .replace(/,/g, '')
  const parsed = Number(normalized)
  if (!Number.isFinite(parsed)) {
    return null
  }
  return parsed
}

function parseDraftValue(
  def: AssumptionFieldDef,
  rawValue: string,
  cadence: IncomeCadence,
): string | number | null {
  const trimmed = rawValue.trim()
  if (!trimmed) {
    return null
  }
  if (def.type === 'text') {
    return trimmed
  }
  const parsed = parseNumericInput(trimmed)
  if (parsed == null) {
    throw new Error(`Enter a valid value for ${def.label.toLowerCase()}.`)
  }
  if (def.type === 'integer') {
    return Math.round(parsed)
  }
  if (def.supportsCadence) {
    return monthlyValueFromCadence(parsed, cadence)
  }
  if (def.type === 'percent' && def.percentStorage === 'fraction') {
    return parsed / 100
  }
  return parsed
}

function rawCadenceValue(rawValue: string) {
  return rawValue.trim() ? parseNumericInput(rawValue) : null
}

function parseResolvedValue(def: AssumptionFieldDef, value: string | null) {
  if (!value) {
    return null
  }
  if (def.type === 'text') {
    return value
  }
  const parsed = parseNumericInput(value)
  if (parsed == null) {
    return null
  }
  return def.type === 'integer' ? Math.round(parsed) : parsed
}

function statusChipColor(kind: 'found' | 'confirmed') {
  return kind === 'confirmed'
    ? 'border-gain/30 bg-gain/10 text-gain'
    : 'border-warning/30 bg-warning/12 text-warning'
}

export function MoneyAssumptionsDrawer({
  profile,
  resolvedValues,
  facts,
  planningContent,
}: {
  profile: HouseholdProfile
  resolvedValues: HouseholdResolvedValue[]
  facts: HouseholdConfirmedFact[]
  planningContent?: ReactNode
}) {
  const updateProfile = useUpdateHouseholdProfile()
  const confirmFact = useConfirmFact()
  const metaMap = useMemo(() => assumptionMetaMap(facts), [facts])
  const resolvedMap = useMemo(
    () => new Map(resolvedValues.map((value) => [value.fieldName, value])),
    [resolvedValues],
  )
  const [draftValues, setDraftValues] = useState<Record<string, string>>({})
  const [draftCadences, setDraftCadences] = useState<
    Record<string, IncomeCadence>
  >({})
  const [settingsField, setSettingsField] = useState<AssumptionFieldDef | null>(
    null,
  )
  const [noteInput, setNoteInput] = useState('')
  const [settingsDisabled, setSettingsDisabled] = useState(false)

  function assumptionMetaValue(
    def: AssumptionFieldDef,
    cadence: IncomeCadence,
  ) {
    const rawValue = rawCadenceValue(draftValues[def.fieldName] ?? '')
    return serializeAssumptionMeta({
      note: metaMap.get(def.fieldName)?.note ?? '',
      disabled: false,
      cadence,
      rawValue: def.supportsCadence ? rawValue : null,
    })
  }

  useEffect(() => {
    const nextValues: Record<string, string> = {}
    const nextCadences: Record<string, IncomeCadence> = {}
    for (const def of assumptionFields) {
      const meta = metaMap.get(def.fieldName)
      const cadence = def.supportsCadence
        ? (meta?.cadence ?? 'monthly')
        : 'monthly'
      nextCadences[def.fieldName] = cadence
      const currentValue = profile[def.profileKey]
      if (def.supportsCadence && typeof currentValue === 'number') {
        const raw =
          meta?.rawValue ??
          cadenceValueFromMonthly(currentValue, cadence) ??
          null
        nextValues[def.fieldName] = raw == null ? '' : String(raw)
        continue
      }
      if (
        def.type === 'percent' &&
        def.percentStorage === 'fraction' &&
        typeof currentValue === 'number'
      ) {
        nextValues[def.fieldName] = String(currentValue * 100)
        continue
      }
      nextValues[def.fieldName] =
        currentValue == null || currentValue === '' ? '' : String(currentValue)
    }
    setDraftValues(nextValues)
    setDraftCadences(nextCadences)
  }, [metaMap, profile])

  function openSettings(def: AssumptionFieldDef) {
    const meta = metaMap.get(def.fieldName)
    setSettingsField(def)
    setNoteInput(meta?.note ?? '')
    setSettingsDisabled(meta?.disabled === true)
  }

  async function saveValue(def: AssumptionFieldDef) {
    try {
      const cadence = draftCadences[def.fieldName] ?? 'monthly'
      const parsedValue = parseDraftValue(
        def,
        draftValues[def.fieldName] ?? '',
        cadence,
      )
      const updatePayload = {
        [def.profileKey]: parsedValue,
      } as HouseholdProfileUpdate
      await Promise.all([
        updateProfile.mutateAsync(updatePayload),
        confirmFact.mutateAsync({
          factKey: `${ASSUMPTION_META_PREFIX}${def.fieldName}`,
          factValue: serializeAssumptionMeta({
            note: metaMap.get(def.fieldName)?.note ?? '',
            disabled: false,
            cadence,
            rawValue: def.supportsCadence
              ? rawCadenceValue(draftValues[def.fieldName] ?? '')
              : null,
          }),
        }),
      ])
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to save assumption.',
      )
    }
  }

  async function acceptFoundValue(def: AssumptionFieldDef) {
    const resolved = resolvedMap.get(def.fieldName)
    const parsed = parseResolvedValue(def, resolved?.value ?? null)
    if (parsed == null) {
      toast.error('No found value is available to accept yet.')
      return
    }
    const cadence = draftCadences[def.fieldName] ?? 'monthly'
    await Promise.all([
      updateProfile.mutateAsync({
        [def.profileKey]: parsed,
      } as HouseholdProfileUpdate),
      confirmFact.mutateAsync({
        factKey: `${ASSUMPTION_META_PREFIX}${def.fieldName}`,
        factValue: serializeAssumptionMeta({
          note: metaMap.get(def.fieldName)?.note ?? '',
          disabled: false,
          cadence,
          rawValue:
            def.supportsCadence && typeof parsed === 'number'
              ? cadenceValueFromMonthly(parsed, cadence)
              : null,
        }),
      }),
    ])
  }

  async function saveSettings() {
    if (!settingsField) {
      return
    }
    if (settingsDisabled && !noteInput.trim()) {
      toast.error('Add a note before hiding this item.')
      return
    }
    const cadence = draftCadences[settingsField.fieldName] ?? 'monthly'
    await confirmFact.mutateAsync({
      factKey: `${ASSUMPTION_META_PREFIX}${settingsField.fieldName}`,
      factValue: serializeAssumptionMeta({
        note: noteInput.trim(),
        disabled: settingsDisabled,
        cadence,
        rawValue: settingsField.supportsCadence
          ? rawCadenceValue(draftValues[settingsField.fieldName] ?? '')
          : null,
      }),
    })
    if (settingsDisabled) {
      await updateProfile.mutateAsync({
        [settingsField.profileKey]: null,
      } as HouseholdProfileUpdate)
    }
    setSettingsField(null)
  }

  const activeFields = assumptionFields.filter(
    (def) => metaMap.get(def.fieldName)?.disabled !== true,
  )
  const hiddenFields = assumptionFields.filter(
    (def) => metaMap.get(def.fieldName)?.disabled === true,
  )
  const draftsReady = activeFields.every((def) => def.fieldName in draftValues)

  async function saveAllValues() {
    try {
      const updatePayload: Record<string, string | number | null> = {}
      const cadenceMetaUpdates: Array<{
        factKey: string
        factValue: string
      }> = []

      for (const def of activeFields) {
        const cadence = draftCadences[def.fieldName] ?? 'monthly'
        updatePayload[def.profileKey] = parseDraftValue(
          def,
          draftValues[def.fieldName] ?? '',
          cadence,
        )
        if (def.supportsCadence) {
          cadenceMetaUpdates.push({
            factKey: `${ASSUMPTION_META_PREFIX}${def.fieldName}`,
            factValue: assumptionMetaValue(def, cadence),
          })
        }
      }

      await updateProfile.mutateAsync(updatePayload as HouseholdProfileUpdate)
      await Promise.all(
        cadenceMetaUpdates.map((meta) => confirmFact.mutateAsync(meta)),
      )
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to save assumptions.',
      )
    }
  }

  return (
    <div className="space-y-5">
      <SectionCard
        variant="surface"
        title="Assumptions"
        description="One compact place to confirm what Jenny found, override it when needed, add notes, and hide anything that should not influence decisions."
      >
        <div className="grid gap-3 lg:grid-cols-4">
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Found values
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {
                activeFields.filter(
                  (def) => resolvedMap.get(def.fieldName)?.value != null,
                ).length
              }
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Confirmed values
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {
                activeFields.filter((def) => profile[def.profileKey] != null)
                  .length
              }
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Hidden items
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {hiddenFields.length}
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Guidance
            </p>
            <p className="mt-3 text-sm leading-6 text-text-muted">
              Yellow means Jenny found a value from evidence. Green means you
              confirmed it or supplied a better one.
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Manual inputs"
        description="Edit several fields, then save all changes at once. Currency fields accept commas and dollar signs."
        actions={
          <Button
            type="button"
            size="sm"
            onClick={() => void saveAllValues()}
            disabled={
              !draftsReady || updateProfile.isPending || confirmFact.isPending
            }
          >
            {updateProfile.isPending || confirmFact.isPending
              ? 'Saving…'
              : 'Save all changes'}
          </Button>
        }
        padding="none"
        className="overflow-hidden"
      >
        <div className="overflow-auto">
          <table className="w-full min-w-[1080px] border-separate border-spacing-0 text-sm">
            <thead className="bg-bg/95 backdrop-blur">
              <tr>
                <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Item
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Found / recommendation
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Confirmed value
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Your input
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {activeFields.map((def) => {
                const resolved = resolvedMap.get(def.fieldName)
                const cadence = draftCadences[def.fieldName] ?? 'monthly'
                const currentValue = profile[def.profileKey]
                return (
                  <tr
                    key={def.fieldName}
                    className="align-top hover:bg-surface-muted/10"
                  >
                    <td className="border-b border-border/20 px-4 py-3">
                      <p className="font-medium text-text">{def.label}</p>
                      <p className="mt-1 text-sm text-text-muted">{def.hint}</p>
                    </td>
                    <td className="border-b border-border/20 px-4 py-3">
                      {resolved?.value != null ? (
                        <div
                          className={`inline-flex rounded-full border px-3 py-1 text-sm ${statusChipColor('found')}`}
                        >
                          {formatResolvedValue(resolved)}
                        </div>
                      ) : (
                        <span className="text-text-muted">
                          Waiting on more evidence
                        </span>
                      )}
                      {resolved?.rationale ? (
                        <p className="mt-2 text-sm text-text-muted">
                          {resolved.rationale}
                        </p>
                      ) : null}
                    </td>
                    <td className="border-b border-border/20 px-4 py-3">
                      {currentValue != null && currentValue !== '' ? (
                        <div
                          className={`inline-flex rounded-full border px-3 py-1 text-sm ${statusChipColor('confirmed')}`}
                        >
                          {formatCurrentValue(def, currentValue)}
                        </div>
                      ) : (
                        <span className="text-text-muted">Not confirmed</span>
                      )}
                      {metaMap.get(def.fieldName)?.note ? (
                        <p className="mt-2 text-sm text-text-muted">
                          {metaMap.get(def.fieldName)?.note}
                        </p>
                      ) : null}
                    </td>
                    <td className="border-b border-border/20 px-4 py-3">
                      <div className="space-y-2">
                        <Input
                          inputMode={
                            def.type === 'text'
                              ? 'text'
                              : def.type === 'integer'
                                ? 'numeric'
                                : 'decimal'
                          }
                          value={draftValues[def.fieldName] ?? ''}
                          onChange={(event) =>
                            setDraftValues((current) => ({
                              ...current,
                              [def.fieldName]: event.target.value,
                            }))
                          }
                          placeholder={def.placeholder}
                        />
                        {def.supportsCadence ? (
                          <Select
                            value={cadence}
                            onValueChange={(value) =>
                              setDraftCadences((current) => ({
                                ...current,
                                [def.fieldName]: value as IncomeCadence,
                              }))
                            }
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Cadence" />
                            </SelectTrigger>
                            <SelectContent>
                              {cadenceOptions.map((option) => (
                                <SelectItem
                                  key={option.value}
                                  value={option.value}
                                >
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : null}
                      </div>
                    </td>
                    <td className="border-b border-border/20 px-4 py-3">
                      <div className="flex flex-col items-end gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => void saveValue(def)}
                          disabled={
                            updateProfile.isPending || confirmFact.isPending
                          }
                        >
                          Save value
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => void acceptFoundValue(def)}
                          disabled={
                            resolved?.value == null ||
                            updateProfile.isPending ||
                            confirmFact.isPending
                          }
                        >
                          Accept found value
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => openSettings(def)}
                        >
                          Note / hide
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {hiddenFields.length > 0 ? (
        <SectionCard
          variant="surface"
          title="Hidden assumptions"
          description="These items are currently excluded because you marked them as irrelevant or noisy."
        >
          <div className="flex flex-wrap gap-2">
            {hiddenFields.map((def) => (
              <button
                key={def.fieldName}
                type="button"
                onClick={() => openSettings(def)}
                className="rounded-full border border-border/35 bg-surface-muted/20 px-3 py-2 text-sm text-text transition-colors hover:border-border/60"
              >
                {def.label}
                {metaMap.get(def.fieldName)?.note
                  ? ` · ${metaMap.get(def.fieldName)?.note}`
                  : ''}
              </button>
            ))}
          </div>
        </SectionCard>
      ) : null}

      {planningContent ? (
        <details className="rounded-2xl border border-border/35 bg-surface-muted/10 p-4">
          <summary className="cursor-pointer list-none text-sm font-semibold text-text">
            Jenny planning workbook
          </summary>
          <div className="mt-4">{planningContent}</div>
        </details>
      ) : null}

      <Dialog
        open={settingsField != null}
        onOpenChange={(open) => {
          if (!open) {
            setSettingsField(null)
          }
        }}
      >
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{settingsField?.label ?? 'Assumption'}</DialogTitle>
            <DialogDescription>
              Add context for Jenny and agents, or hide this item so it stops
              using space and steering calculations.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="assumption-note">Note</Label>
              <Textarea
                id="assumption-note"
                value={noteInput}
                onChange={(event) => setNoteInput(event.target.value)}
                rows={5}
                placeholder="What should Jenny know about this item? Why should it be hidden, overridden, or treated carefully?"
              />
            </div>
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-text">
                    Hide this item
                  </p>
                  <p className="mt-1 text-sm text-text-muted">
                    Hidden items require a note and are cleared from the
                    confirmed profile.
                  </p>
                </div>
                <Button
                  type="button"
                  variant={settingsDisabled ? 'default' : 'outline'}
                  onClick={() => setSettingsDisabled((current) => !current)}
                >
                  {settingsDisabled ? 'Hidden' : 'Visible'}
                </Button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setSettingsField(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void saveSettings()}
              disabled={confirmFact.isPending || updateProfile.isPending}
            >
              Save note
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
