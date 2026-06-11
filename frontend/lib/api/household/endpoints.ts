import { del, get, post, put } from '../client'
import type {
  HouseholdPlanningSnapshot,
  HouseholdPlanningUpdate,
} from '../household-planning'
import type {
  HouseholdAccountHoldings,
  HouseholdConfirmedFact,
  HouseholdDocumentList,
  HouseholdFinanceDashboard,
  HouseholdLedger,
  HouseholdLedgerParams,
  HouseholdNetWorthTrend,
  HouseholdProfile,
  HouseholdProfileUpdate,
  HouseholdQuestion,
  HouseholdQuestionAnswer,
  HouseholdQuestionList,
  HouseholdSpendingView,
  HouseholdTrackedAccount,
  HouseholdTrackedAccountInput,
  HouseholdTransactionCategoryUpdate,
  ManualHoldingsReplaceInput,
  RetirementAllocationScenario,
  RetirementAllocationScenarioInput,
  RetirementPreview,
  RetirementPreviewRequest,
} from './types'

type Endpoint<P extends unknown[], T> = (...args: P) => Promise<T>

function getEndpoint<T>(path: string): Endpoint<[RequestInit?], T> {
  return (options: RequestInit = {}) => get<T>(path, options)
}

function postEndpoint<Payload, T>(path: string): Endpoint<[Payload], T> {
  return (payload: Payload) => post<T>(path, payload)
}

export const fetchHouseholdDashboard = getEndpoint<HouseholdFinanceDashboard>(
  '/api/household/dashboard',
)
export const fetchHouseholdProfile = getEndpoint<HouseholdProfile>(
  '/api/household/profile',
)
export const updateHouseholdProfile = postEndpoint<
  HouseholdProfileUpdate,
  HouseholdProfile
>('/api/household/profile')
export const fetchHouseholdPlanning = getEndpoint<HouseholdPlanningSnapshot>(
  '/api/household/planning',
)
export const updateHouseholdPlanning = postEndpoint<
  HouseholdPlanningUpdate,
  HouseholdPlanningSnapshot
>('/api/household/planning')
export const fetchHouseholdDocuments = getEndpoint<HouseholdDocumentList>(
  '/api/intake/evidence',
)
export const fetchHouseholdQuestions = getEndpoint<HouseholdQuestionList>(
  '/api/household/questions',
)
export const createHouseholdTrackedAccount = postEndpoint<
  HouseholdTrackedAccountInput,
  HouseholdTrackedAccount
>('/api/household/accounts')
export const fetchConfirmedFacts = getEndpoint<HouseholdConfirmedFact[]>(
  '/api/household/facts',
)

export async function fetchHouseholdLedger(
  params?: HouseholdLedgerParams,
  options: RequestInit = {},
): Promise<HouseholdLedger> {
  const search = new URLSearchParams()
  if (params?.window) search.set('window', params.window)
  if (params?.kind) search.set('kind', params.kind)
  if (params?.status) search.set('status', params.status)
  if (params?.account) search.set('account', params.account)
  if (params?.search) search.set('search', params.search)
  if (params?.sort) search.set('sort', params.sort)
  if (params?.sortDir) search.set('sort_dir', params.sortDir)
  if (params?.limit != null) search.set('limit', String(params.limit))
  if (params?.offset != null) search.set('offset', String(params.offset))
  const query = search.toString()
  return get<HouseholdLedger>(
    query ? `/api/household/ledger?${query}` : '/api/household/ledger',
    options,
  )
}

export async function fetchHouseholdSpending(
  params?: { window?: string },
  options: RequestInit = {},
): Promise<HouseholdSpendingView> {
  const search = new URLSearchParams()
  if (params?.window) search.set('window', params.window)
  const query = search.toString()
  return get<HouseholdSpendingView>(
    query ? `/api/household/spending?${query}` : '/api/household/spending',
    options,
  )
}

export async function fetchHouseholdNetWorthTrend(
  params?: { days?: number },
  options: RequestInit = {},
): Promise<HouseholdNetWorthTrend> {
  const search = new URLSearchParams()
  if (params?.days != null) search.set('days', String(params.days))
  const query = search.toString()
  return get<HouseholdNetWorthTrend>(
    query
      ? `/api/household/net-worth-trend?${query}`
      : '/api/household/net-worth-trend',
    options,
  )
}

export async function fetchRetirementPreview(
  payload: RetirementPreviewRequest,
  options: RequestInit = {},
): Promise<RetirementPreview> {
  return post<RetirementPreview>('/api/retirement/preview', payload, options)
}

export async function fetchAllocationScenarios(
  options: RequestInit = {},
): Promise<RetirementAllocationScenario[]> {
  return get<RetirementAllocationScenario[]>(
    '/api/retirement/allocation-scenarios',
    options,
  )
}

export async function replaceAllocationScenarios(
  scenarios: RetirementAllocationScenarioInput[],
  options: RequestInit = {},
): Promise<RetirementAllocationScenario[]> {
  return put<RetirementAllocationScenario[]>(
    '/api/retirement/allocation-scenarios',
    { scenarios },
    options,
  )
}

export async function fetchHouseholdAccountHoldings(
  householdAccountId: string,
  options: RequestInit = {},
): Promise<HouseholdAccountHoldings> {
  return get<HouseholdAccountHoldings>(
    `/api/household/accounts/${householdAccountId}/holdings`,
    options,
  )
}

export async function replaceHouseholdAccountHoldings(
  householdAccountId: string,
  payload: ManualHoldingsReplaceInput,
): Promise<HouseholdAccountHoldings> {
  return put<HouseholdAccountHoldings>(
    `/api/household/accounts/${householdAccountId}/holdings`,
    payload,
  )
}

export async function updateHouseholdTrackedAccount(
  accountId: string,
  payload: HouseholdTrackedAccountInput,
): Promise<HouseholdTrackedAccount> {
  return put<HouseholdTrackedAccount>(
    `/api/household/accounts/${accountId}`,
    payload,
  )
}

export async function deleteHouseholdTrackedAccount(
  accountId: string,
): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/api/household/accounts/${accountId}`)
}

export async function deleteHouseholdDocument(
  documentId: string,
): Promise<void> {
  await del<void>(`/api/intake/evidence/${documentId}`)
}

export async function answerHouseholdQuestion(
  questionId: string,
  payload: HouseholdQuestionAnswer,
): Promise<HouseholdQuestion> {
  return post<HouseholdQuestion>(
    `/api/household/questions/${questionId}/answer`,
    payload,
  )
}

export async function confirmFact(
  factKey: string,
  factValue: string,
): Promise<HouseholdConfirmedFact> {
  return post<HouseholdConfirmedFact>('/api/household/facts', {
    factKey,
    factValue,
  })
}

export async function askJenny(question: string): Promise<HouseholdQuestion> {
  return post<HouseholdQuestion>('/api/household/ask', { question })
}

export async function categorizeHouseholdTransaction(
  transactionId: string,
  payload: HouseholdTransactionCategoryUpdate,
): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>(
    `/api/household/transactions/${transactionId}/categorize`,
    payload,
  )
}
