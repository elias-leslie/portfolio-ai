import { del, get, post, postForm, put } from '../client'
import type {
  CardIntakeResult,
  CardRanking,
  CatalogResearchResult,
  CreditCardCreate,
  CreditCardProduct,
  CreditCardUpdate,
  HouseholdCreditCard,
  RankingRequest,
  RotationPlanView,
  RotationRequest,
  SoftCharge,
  SoftChargeCreate,
} from './types'

const CARDS_BASE = '/api/household/cards'

// ------------------------------------------------------------------ catalog

export function fetchCardCatalog(
  options: RequestInit = {},
): Promise<CreditCardProduct[]> {
  return get<CreditCardProduct[]>(`${CARDS_BASE}/catalog`, options)
}

// -------------------------------------------------------------- owned cards

export function fetchOwnedCards(
  options: RequestInit = {},
): Promise<HouseholdCreditCard[]> {
  return get<HouseholdCreditCard[]>(CARDS_BASE, options)
}

export function createOwnedCard(
  payload: CreditCardCreate,
): Promise<HouseholdCreditCard> {
  return post<HouseholdCreditCard>(CARDS_BASE, payload)
}

export function updateOwnedCard(
  cardId: string,
  payload: CreditCardUpdate,
): Promise<HouseholdCreditCard> {
  return put<HouseholdCreditCard>(`${CARDS_BASE}/${cardId}`, payload)
}

export function activateOwnedCard(
  cardId: string,
): Promise<HouseholdCreditCard> {
  return post<HouseholdCreditCard>(`${CARDS_BASE}/${cardId}/activate`)
}

export async function deleteOwnedCard(cardId: string): Promise<void> {
  await del<void>(`${CARDS_BASE}/${cardId}`)
}

// ------------------------------------------------------- ranking / rotation

export function fetchCardRankings(
  payload: RankingRequest,
  options: RequestInit = {},
): Promise<CardRanking> {
  return post<CardRanking>(`${CARDS_BASE}/rankings`, payload, options)
}

export function fetchRotationPlan(
  payload: RotationRequest,
  options: RequestInit = {},
): Promise<RotationPlanView> {
  return post<RotationPlanView>(`${CARDS_BASE}/rotation-plan`, payload, options)
}

// ------------------------------------------------------------- offer intake

export function intakeCardOffer(
  file: File,
  documentType = 'offer_screenshot',
): Promise<CardIntakeResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('document_type', documentType)
  return postForm<CardIntakeResult>(`${CARDS_BASE}/intake`, form)
}

// --------------------------------------------------------- catalog research

export function refreshCatalogResearch(): Promise<CatalogResearchResult> {
  return post<CatalogResearchResult>(`${CARDS_BASE}/research/refresh`)
}

// ------------------------------------------------------------- soft charges

export function createSoftCharge(
  payload: SoftChargeCreate,
): Promise<SoftCharge> {
  const form = new FormData()
  form.append('amount', String(payload.amount))
  form.append('description', payload.description)
  if (payload.merchant) form.append('merchant', payload.merchant)
  if (payload.category) form.append('category', payload.category)
  if (payload.essentiality) form.append('essentiality', payload.essentiality)
  if (payload.occurredAt) form.append('occurred_at', payload.occurredAt)
  if (payload.householdAccountId)
    form.append('household_account_id', payload.householdAccountId)
  if (payload.receipt) form.append('receipt', payload.receipt)
  return postForm<SoftCharge>(`${CARDS_BASE}/soft-charges`, form)
}

export function fetchSoftCharges(
  status?: string,
  options: RequestInit = {},
): Promise<SoftCharge[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  return get<SoftCharge[]>(`${CARDS_BASE}/soft-charges${query}`, options)
}

export function matchSoftCharge(
  softChargeId: string,
  plaidTransactionId: string,
): Promise<SoftCharge> {
  const form = new FormData()
  form.append('plaid_transaction_id', plaidTransactionId)
  return postForm<SoftCharge>(
    `${CARDS_BASE}/soft-charges/${softChargeId}/match`,
    form,
  )
}

export async function deleteSoftCharge(softChargeId: string): Promise<void> {
  await del<void>(`${CARDS_BASE}/soft-charges/${softChargeId}`)
}
