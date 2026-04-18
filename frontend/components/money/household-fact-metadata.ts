import type { HouseholdConfirmedFact } from '@/lib/api/household'

export type IncomeCadence = 'monthly' | 'biweekly' | 'annual'

export interface AssumptionMeta {
  note: string
  disabled: boolean
  cadence?: IncomeCadence
  rawValue?: number | null
}

export interface CategoryBudgetMeta {
  category: string
  note: string
  disabled: boolean
  monthlyTarget?: number | null
  source?: 'found' | 'accepted' | 'manual' | null
}

export const ASSUMPTION_META_PREFIX = 'assumption_meta:'
export const CATEGORY_BUDGET_PREFIX = 'category_budget:'

function safeParseJson<T>(value: string, fallback: T): T {
  try {
    const parsed = JSON.parse(value)
    return (parsed as T) ?? fallback
  } catch {
    return fallback
  }
}

export function monthlyValueFromCadence(
  value: number | null | undefined,
  cadence: IncomeCadence,
): number | null {
  if (value == null || Number.isNaN(value)) {
    return null
  }
  if (cadence === 'annual') {
    return value / 12
  }
  if (cadence === 'biweekly') {
    return (value * 26) / 12
  }
  return value
}

export function cadenceValueFromMonthly(
  value: number | null | undefined,
  cadence: IncomeCadence,
): number | null {
  if (value == null || Number.isNaN(value)) {
    return null
  }
  if (cadence === 'annual') {
    return value * 12
  }
  if (cadence === 'biweekly') {
    return (value * 12) / 26
  }
  return value
}

export function assumptionMetaMap(facts: HouseholdConfirmedFact[]) {
  const map = new Map<string, AssumptionMeta>()
  for (const fact of facts) {
    if (!fact.factKey.startsWith(ASSUMPTION_META_PREFIX)) {
      continue
    }
    const fieldName = fact.factKey.slice(ASSUMPTION_META_PREFIX.length)
    const parsed = safeParseJson<AssumptionMeta>(fact.factValue, {
      note: '',
      disabled: false,
    })
    map.set(fieldName, {
      note: parsed.note ?? '',
      disabled: parsed.disabled === true,
      cadence:
        parsed.cadence === 'monthly' ||
        parsed.cadence === 'biweekly' ||
        parsed.cadence === 'annual'
          ? parsed.cadence
          : undefined,
      rawValue:
        typeof parsed.rawValue === 'number' && Number.isFinite(parsed.rawValue)
          ? parsed.rawValue
          : null,
    })
  }
  return map
}

export function categoryBudgetMetaMap(facts: HouseholdConfirmedFact[]) {
  const map = new Map<string, CategoryBudgetMeta>()
  for (const fact of facts) {
    if (!fact.factKey.startsWith(CATEGORY_BUDGET_PREFIX)) {
      continue
    }
    const category = fact.factKey.slice(CATEGORY_BUDGET_PREFIX.length)
    const parsed = safeParseJson<CategoryBudgetMeta>(fact.factValue, {
      category,
      note: '',
      disabled: false,
    })
    map.set(category, {
      category,
      note: parsed.note ?? '',
      disabled: parsed.disabled === true,
      monthlyTarget:
        typeof parsed.monthlyTarget === 'number' &&
        Number.isFinite(parsed.monthlyTarget)
          ? parsed.monthlyTarget
          : null,
      source:
        parsed.source === 'found' ||
        parsed.source === 'accepted' ||
        parsed.source === 'manual'
          ? parsed.source
          : null,
    })
  }
  return map
}

export function serializeAssumptionMeta(meta: AssumptionMeta): string {
  return JSON.stringify({
    note: meta.note,
    disabled: meta.disabled,
    cadence: meta.cadence ?? 'monthly',
    rawValue: meta.rawValue ?? null,
  })
}

export function serializeCategoryBudgetMeta(meta: CategoryBudgetMeta): string {
  return JSON.stringify({
    category: meta.category,
    note: meta.note,
    disabled: meta.disabled,
    monthlyTarget: meta.monthlyTarget ?? null,
    source: meta.source ?? null,
  })
}
