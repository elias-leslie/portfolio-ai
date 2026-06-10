import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  activateOwnedCard,
  type CreditCardCreate,
  type CreditCardUpdate,
  createOwnedCard,
  createSoftCharge,
  deleteOwnedCard,
  deleteSoftCharge,
  fetchCardCatalog,
  fetchCardRankings,
  fetchOwnedCards,
  fetchRotationPlan,
  fetchSoftCharges,
  intakeCardOffer,
  matchSoftCharge,
  type RankingRequest,
  type RotationRequest,
  refreshCatalogResearch,
  type SoftChargeCreate,
  updateOwnedCard,
} from '@/lib/api/cards'

const CARDS_STALE_MS = 1000 * 60 * 5

async function refreshCardQueries(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  await queryClient.invalidateQueries({ queryKey: ['cards'], exact: false })
}

/** Soft charges mirror into the canonical ledger, so household budget/ledger
 * views must refresh alongside the cards queries. */
async function refreshCardAndHouseholdQueries(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  await refreshCardQueries(queryClient)
  await queryClient.resetQueries({ queryKey: ['household'], exact: false })
}

export function useCardCatalog() {
  return useQuery({
    queryKey: ['cards', 'catalog'],
    queryFn: ({ signal }) => fetchCardCatalog({ signal }),
    staleTime: CARDS_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useOwnedCards() {
  return useQuery({
    queryKey: ['cards', 'owned'],
    queryFn: ({ signal }) => fetchOwnedCards({ signal }),
    staleTime: CARDS_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useCardRankings(params: RankingRequest) {
  return useQuery({
    queryKey: ['cards', 'rankings', params],
    queryFn: ({ signal }) => fetchCardRankings(params, { signal }),
    staleTime: CARDS_STALE_MS,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
  })
}

export function useRotationPlan(params: RotationRequest) {
  return useQuery({
    queryKey: ['cards', 'rotation-plan', params],
    queryFn: ({ signal }) => fetchRotationPlan(params, { signal }),
    staleTime: CARDS_STALE_MS,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
  })
}

export function useSoftCharges(status?: string) {
  return useQuery({
    queryKey: ['cards', 'soft-charges', status ?? 'all'],
    queryFn: ({ signal }) => fetchSoftCharges(status, { signal }),
    staleTime: CARDS_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useCreateCard() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreditCardCreate) => createOwnedCard(payload),
    onSuccess: async () => {
      await refreshCardQueries(queryClient)
      toast.success('Card added to the household wallet.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to add card')
    },
  })
}

export function useUpdateCard() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      cardId,
      payload,
    }: {
      cardId: string
      payload: CreditCardUpdate
    }) => updateOwnedCard(cardId, payload),
    onSuccess: async () => {
      await refreshCardQueries(queryClient)
      toast.success('Card updated.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to update card',
      )
    },
  })
}

export function useActivateCard() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (cardId: string) => activateOwnedCard(cardId),
    onSuccess: async (card) => {
      await refreshCardQueries(queryClient)
      toast.success(
        `${card.product?.productName ?? 'Card'} is now the primary rotating card.`,
      )
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to activate card',
      )
    },
  })
}

export function useDeleteCard() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (cardId: string) => deleteOwnedCard(cardId),
    onSuccess: async () => {
      await refreshCardQueries(queryClient)
      toast.success('Card removed.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to remove card',
      )
    },
  })
}

export function useIntakeCardOffer() {
  return useMutation({
    mutationFn: ({
      file,
      documentType,
    }: {
      file: File
      documentType?: string
    }) => intakeCardOffer(file, documentType),
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to extract card offer terms',
      )
    },
  })
}

export function useRefreshCatalogResearch() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => refreshCatalogResearch(),
    onSuccess: async (result) => {
      await refreshCardQueries(queryClient)
      toast.success(
        `Catalog research complete: ${result.updatesApplied} update${
          result.updatesApplied === 1 ? '' : 's'
        } applied, ${result.candidatesAdded} candidate${
          result.candidatesAdded === 1 ? '' : 's'
        } added.`,
      )
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Catalog research failed',
      )
    },
  })
}

export function useCreateSoftCharge() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: SoftChargeCreate) => createSoftCharge(payload),
    onSuccess: async (softCharge) => {
      await refreshCardAndHouseholdQueries(queryClient)
      toast.success(
        `Soft charge logged: ${softCharge.description} — it counts toward the budget now.`,
      )
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to log soft charge',
      )
    },
  })
}

export function useMatchSoftCharge() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      softChargeId,
      plaidTransactionId,
    }: {
      softChargeId: string
      plaidTransactionId: string
    }) => matchSoftCharge(softChargeId, plaidTransactionId),
    onSuccess: async () => {
      await refreshCardAndHouseholdQueries(queryClient)
      toast.success('Soft charge matched to the bank transaction.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to match soft charge',
      )
    },
  })
}

export function useDeleteSoftCharge() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (softChargeId: string) => deleteSoftCharge(softChargeId),
    onSuccess: async () => {
      await refreshCardAndHouseholdQueries(queryClient)
      toast.success('Soft charge removed.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to remove soft charge',
      )
    },
  })
}
