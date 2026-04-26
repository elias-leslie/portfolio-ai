import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  answerHouseholdQuestion,
  askJenny,
  categorizeHouseholdTransaction,
  confirmFact,
  createHouseholdTrackedAccount,
  deleteHouseholdTrackedAccount,
  fetchConfirmedFacts,
  fetchHouseholdDashboard,
  fetchHouseholdDocuments,
  fetchHouseholdLedger,
  fetchHouseholdSpending,
  type HouseholdDocumentUpload,
  type HouseholdPlanningUpdate,
  type HouseholdProfileUpdate,
  type HouseholdTrackedAccountInput,
  resolveHouseholdTransactionDateIssue,
  updateHouseholdPlanning,
  updateHouseholdProfile,
  updateHouseholdTrackedAccount,
  uploadHouseholdDocument,
} from '@/lib/api/household'

async function refreshHouseholdQueries(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  await queryClient.resetQueries({
    queryKey: ['household'],
    exact: false,
  })
}

export function useHouseholdDashboard() {
  return useQuery({
    queryKey: ['household', 'dashboard'],
    queryFn: fetchHouseholdDashboard,
    staleTime: 0,
    refetchInterval: 1000 * 30,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
  })
}

export function useHouseholdDocuments() {
  return useQuery({
    queryKey: ['household', 'documents'],
    queryFn: fetchHouseholdDocuments,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
  })
}

export function useHouseholdFacts() {
  return useQuery({
    queryKey: ['household', 'facts'],
    queryFn: fetchConfirmedFacts,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
  })
}

export function useHouseholdLedger(params?: {
  window?: string
  kind?: string
  limit?: number
}) {
  return useQuery({
    queryKey: ['household', 'ledger', params ?? {}],
    queryFn: () => fetchHouseholdLedger(params),
    staleTime: 0,
    refetchInterval: 1000 * 30,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
  })
}

export function useHouseholdSpending(params?: { window?: string }) {
  return useQuery({
    queryKey: ['household', 'spending', params ?? {}],
    queryFn: () => fetchHouseholdSpending(params),
    staleTime: 0,
    refetchInterval: 1000 * 30,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
  })
}

export function useUpdateHouseholdProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdProfileUpdate) =>
      updateHouseholdProfile(payload),
    onSuccess: async (profile) => {
      queryClient.setQueryData(['household', 'profile'], profile)
      await refreshHouseholdQueries(queryClient)
      toast.success('Household profile updated.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to update household profile',
      )
    },
  })
}

export function useUpdateHouseholdPlanning() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdPlanningUpdate) =>
      updateHouseholdPlanning(payload),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Household planning sections updated.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to update household planning',
      )
    },
  })
}

export function useUploadHouseholdDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdDocumentUpload) =>
      uploadHouseholdDocument(payload),
    onSuccess: async (document) => {
      await refreshHouseholdQueries(queryClient)
      if (document.metadata?.duplicate_detected === true) {
        toast.info(`${document.filename} already exists in evidence intake.`)
        return
      }
      toast.success(`${document.filename} staged for evidence intake.`)
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to upload document',
      )
    },
  })
}

export function useCreateHouseholdTrackedAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdTrackedAccountInput) =>
      createHouseholdTrackedAccount(payload),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Tracked account created.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to create tracked account',
      )
    },
  })
}

export function useUpdateHouseholdTrackedAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      accountId,
      payload,
    }: {
      accountId: string
      payload: HouseholdTrackedAccountInput
    }) => updateHouseholdTrackedAccount(accountId, payload),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Tracked account updated.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to update tracked account',
      )
    },
  })
}

export function useDeleteHouseholdTrackedAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (accountId: string) => deleteHouseholdTrackedAccount(accountId),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Tracked account removed.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to remove tracked account',
      )
    },
  })
}

export function useAnswerHouseholdQuestion() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      questionId,
      answerText,
    }: {
      questionId: string
      answerText: string
    }) => answerHouseholdQuestion(questionId, { answerText }),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Jenny updated the household plan.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to answer Jenny question',
      )
    },
  })
}

export function useConfirmFact() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      factKey,
      factValue,
    }: {
      factKey: string
      factValue: string
    }) => confirmFact(factKey, factValue),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Jenny noted your confirmation.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to confirm fact',
      )
    },
  })
}

export function useAskJenny() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (question: string) => askJenny(question),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Question sent to Jenny.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to send question to Jenny',
      )
    },
  })
}

export function useCategorizeHouseholdTransaction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      transactionId,
      category,
      essentiality,
      applyToMerchant,
    }: {
      transactionId: string
      category: string
      essentiality: string
      applyToMerchant?: boolean
    }) =>
      categorizeHouseholdTransaction(transactionId, {
        category,
        essentiality,
        applyToMerchant,
      }),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Household category confirmed.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to categorize transaction',
      )
    },
  })
}

export function useResolveHouseholdTransactionDateIssue() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      issueId,
      resolution,
      note,
    }: {
      issueId: string
      resolution: string
      note?: string
    }) => resolveHouseholdTransactionDateIssue(issueId, { resolution, note }),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Date issue resolved.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to resolve date issue',
      )
    },
  })
}
