import type { PlanningFocusSection } from '@/components/money/HouseholdPlanningPanels'

export type MoneyUtility = 'planning' | 'data-services'
export type MoneyFocus =
  | 'date-quality'
  | 'clarifications'
  | 'account-coverage'
  | 'discovered-accounts'
  | PlanningFocusSection
export type MoneyIntent = 'evidence' | 'review'

export type MoneyRouteState = {
  openUtility: MoneyUtility | null
  focusedReview: MoneyFocus | null
  selectedAccountId: string | null
  selectedQuestionId: string | null
  selectedIntent: MoneyIntent | null
}

const EMPTY_ROUTE_STATE: MoneyRouteState = {
  openUtility: null,
  focusedReview: null,
  selectedAccountId: null,
  selectedQuestionId: null,
  selectedIntent: null,
}

const planningFocusSections = new Set<string>([
  'household',
  'income',
  'debt',
  'housing',
  'insurance',
  'retirement',
  'expenses',
])

export function isPlanningFocus(
  focus: MoneyFocus | null,
): focus is PlanningFocusSection {
  return Boolean(focus && planningFocusSections.has(focus))
}

function resolveRequestedUtility(value: string | null): MoneyUtility | null {
  return value === 'planning' || value === 'data-services' ? value : null
}

function resolveRequestedFocus(value: string | null): MoneyFocus | null {
  if (
    value === 'date-quality' ||
    value === 'clarifications' ||
    value === 'account-coverage' ||
    value === 'discovered-accounts' ||
    planningFocusSections.has(value ?? '')
  ) {
    return value as MoneyFocus
  }
  return null
}

function resolveRequestedIntent(value: string | null): MoneyIntent | null {
  return value === 'evidence' || value === 'review' ? value : null
}

export function resolveMoneyRouteState(
  searchParams: URLSearchParams,
): MoneyRouteState {
  return {
    openUtility: resolveRequestedUtility(searchParams.get('utility')),
    focusedReview: resolveRequestedFocus(searchParams.get('focus')),
    selectedAccountId: searchParams.get('account'),
    selectedQuestionId: searchParams.get('question'),
    selectedIntent: resolveRequestedIntent(searchParams.get('intent')),
  }
}

export function readMoneyRouteState(): MoneyRouteState {
  if (typeof window === 'undefined') {
    return EMPTY_ROUTE_STATE
  }
  return resolveMoneyRouteState(new URLSearchParams(window.location.search))
}

export function syncUtilityToLocation(
  nextUtility: MoneyUtility | null,
  nextFocus: MoneyFocus | null = null,
) {
  if (typeof window === 'undefined') {
    return
  }
  const nextUrl = new URL(window.location.href)
  if (nextUtility) {
    nextUrl.searchParams.set('utility', nextUtility)
  } else {
    nextUrl.searchParams.delete('utility')
  }
  if (nextUtility && nextFocus) {
    nextUrl.searchParams.set('focus', nextFocus)
  } else {
    nextUrl.searchParams.delete('focus')
  }
  window.history.replaceState(window.history.state, '', nextUrl)
}
