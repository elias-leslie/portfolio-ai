import type {
  HouseholdProfile,
  HouseholdProfileUpdate,
} from '@/lib/api/household'
import { formatCurrency } from '@/lib/formatters'

type AssumptionFieldType =
  | 'currency'
  | 'integer'
  | 'number'
  | 'percent'
  | 'text'

export type AssumptionFieldDef = {
  fieldName: string
  profileKey: keyof HouseholdProfileUpdate & keyof HouseholdProfile
  label: string
  type: AssumptionFieldType
  hint: string
  placeholder?: string
  acceptsFoundValue?: boolean
  supportsCadence?: boolean
  percentStorage?: 'fraction'
  unit?: 'age' | 'years' | 'months'
  min?: number
  max?: number
}

export const assumptionFields: AssumptionFieldDef[] = [
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
    hint: 'What the household aims to take home. Caps are priced off the income anchor on the Budget screen — the median of the last three complete months — not off this figure.',
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
    unit: 'months',
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
    unit: 'age',
    min: 18,
    max: 100,
    profileKey: 'targetRetirementAge',
    label: 'Your retirement age',
    type: 'integer',
    hint: 'The age Jenny should use for preparedness framing.',
    placeholder: '60',
  },
  {
    fieldName: 'target_spouse_retirement_age',
    unit: 'age',
    min: 18,
    max: 100,
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
    unit: 'years',
    min: 1,
    max: 100,
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
    unit: 'age',
    min: 62,
    max: 70,
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
    unit: 'age',
    min: 62,
    max: 70,
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

const fieldMap = new Map(
  assumptionFields.map((field) => [field.fieldName, field]),
)

export function assumptionField(name: string) {
  return fieldMap.get(name)
}

export function validAssumptionValue(
  def: AssumptionFieldDef,
  value: unknown,
): boolean {
  if (def.type === 'text') {
    return (
      typeof value === 'string' &&
      value.trim().length > 0 &&
      !/^(unknown|not set|unavailable|n\/a)$/i.test(value.trim())
    )
  }
  if (typeof value !== 'number' || !Number.isFinite(value)) return false
  if (def.type === 'integer' && !Number.isInteger(value)) return false
  const minimum = def.min ?? 0
  const maximum =
    def.max ??
    (def.type === 'percent'
      ? def.percentStorage === 'fraction'
        ? 1
        : 100
      : Infinity)
  return value >= minimum && value <= maximum
}

export function parseStoredAssumption(
  def: AssumptionFieldDef,
  value: unknown,
): string | number | null {
  if (value == null || String(value).trim() === '') return null
  const parsed = def.type === 'text' ? String(value).trim() : Number(value)
  return validAssumptionValue(def, parsed) ? parsed : null
}

export function formatAssumptionValue(
  def: AssumptionFieldDef,
  value: unknown,
): string {
  const parsed = parseStoredAssumption(def, value)
  if (parsed == null) return 'Not established'
  if (typeof parsed === 'string') {
    if (def.fieldName === 'filing_status') {
      return (
        (
          {
            married_filing_jointly: 'Married filing jointly',
            married_filing_separately: 'Married filing separately',
            single: 'Single',
            head_of_household: 'Head of household',
            qualifying_surviving_spouse: 'Qualifying surviving spouse',
          } as Record<string, string>
        )[parsed] ?? parsed.replaceAll('_', ' ')
      )
    }
    return parsed
  }
  if (def.type === 'currency') return formatCurrency(parsed, { decimals: 0 })
  const display = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 3,
  }).format(def.percentStorage === 'fraction' ? parsed * 100 : parsed)
  if (def.type === 'percent') return `${display}%`
  if (def.unit === 'age') return `Age ${display}`
  if (def.unit) return `${display} ${def.unit}`
  return display
}
