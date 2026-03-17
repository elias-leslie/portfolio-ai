import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  answerHouseholdQuestion,
  askJenny,
  categorizeHouseholdTransaction,
  confirmFact,
  type HouseholdDocumentUpload,
  type HouseholdPlanningUpdate,
  type HouseholdProfileUpdate,
  fetchHouseholdDashboard,
  fetchHouseholdDocuments,
  updateHouseholdPlanning,
  updateHouseholdProfile,
  uploadHouseholdDocument,
} from '@/lib/api/household'

/** Dashboard rebuilds server-side; 60 s keeps the UI fresh without over-fetching. */
const DASHBOARD_STALE_MS = 1000 * 60

/** Documents and questions change on user action; 30 s balances freshness with server load. */
const VOLATILE_STALE_MS = 1000 * 30

export function useHouseholdDashboard() {
  return useQuery({
    queryKey: ['household', 'dashboard'],
    queryFn: fetchHouseholdDashboard,
    staleTime: DASHBOARD_STALE_MS,
  })
}

export function useHouseholdDocuments() {
  return useQuery({
    queryKey: ['household', 'documents'],
    queryFn: fetchHouseholdDocuments,
    staleTime: VOLATILE_STALE_MS,
  })
}

export function useUpdateHouseholdProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdProfileUpdate) => updateHouseholdProfile(payload),
    onSuccess: (profile) => {
      queryClient.setQueryData(['household', 'profile'], profile)
      queryClient.invalidateQueries({ queryKey: ['household'], refetchType: 'active' })
      toast.success('Household profile updated.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to update household profile')
    },
  })
}

export function useUpdateHouseholdPlanning() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdPlanningUpdate) => updateHouseholdPlanning(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['household'], refetchType: 'active' })
      toast.success('Household planning sections updated.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to update household planning')
    },
  })
}

export function useUploadHouseholdDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdDocumentUpload) => uploadHouseholdDocument(payload),
    onSuccess: (document) => {
      queryClient.invalidateQueries({ queryKey: ['household'], refetchType: 'active' })
      if (document.metadata?.duplicate_detected === true) {
        toast.info(`${document.filename} already exists in household intake.`)
        return
      }
      toast.success(`${document.filename} staged for household intake.`)
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to upload document')
    },
  })
}

export function useAnswerHouseholdQuestion() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ questionId, answerText }: { questionId: string; answerText: string }) =>
      answerHouseholdQuestion(questionId, { answerText }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['household'], refetchType: 'active' })
      toast.success('Jenny updated the household plan.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to answer Jenny question')
    },
  })
}

export function useConfirmFact() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ factKey, factValue }: { factKey: string; factValue: string }) =>
      confirmFact(factKey, factValue),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['household'], refetchType: 'active' })
      toast.success('Jenny noted your confirmation.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to confirm fact')
    },
  })
}

export function useAskJenny() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (question: string) => askJenny(question),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['household'], refetchType: 'active' })
      toast.success('Question sent to Jenny.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to send question to Jenny')
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['household'], refetchType: 'active' })
      toast.success('Household category confirmed.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to categorize transaction')
    },
  })
}
