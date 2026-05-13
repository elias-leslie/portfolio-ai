import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  answerHouseholdQuestion,
  askJenny,
  categorizeHouseholdTransaction,
  confirmFact,
  createHouseholdTrackedAccount,
  deleteHouseholdDocument,
  deleteHouseholdTrackedAccount,
  fetchConfirmedFacts,
  fetchHouseholdDashboard,
  fetchHouseholdDocuments,
  fetchHouseholdLedger,
  fetchHouseholdNetWorthTrend,
  fetchHouseholdSpending,
  type HouseholdDocument,
  type HouseholdDocumentUpload,
  type HouseholdPlanningUpdate,
  type HouseholdProfileUpdate,
  type HouseholdTrackedAccountInput,
  updateHouseholdPlanning,
  updateHouseholdProfile,
  updateHouseholdTrackedAccount,
  uploadHouseholdDocument,
  uploadHouseholdDocuments,
} from '@/lib/api/household'

const DOCUMENT_REVIEW_POLL_INTERVAL_MS = 1500
const DOCUMENT_REVIEW_POLL_ATTEMPTS = 40
const HOUSEHOLD_WORKSPACE_STALE_MS = 1000 * 60 * 5
const HOUSEHOLD_MARKET_VALUE_REFRESH_MS = 1000 * 30

async function refreshHouseholdQueries(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  await queryClient.resetQueries({
    queryKey: ['household'],
    exact: false,
  })
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function applicationStatus(document: HouseholdDocument) {
  const summary = document.metadata?.application_summary
  if (!summary || typeof summary !== 'object' || Array.isArray(summary)) {
    return null
  }
  const status = (summary as Record<string, unknown>).status
  return typeof status === 'string' ? status : null
}

function documentApplicationDone(document: HouseholdDocument) {
  if (document.metadata?.duplicate_detected === true) return true
  if (document.status === 'failed' || document.reviewStatus === 'failed') {
    return true
  }
  if (applicationStatus(document)) return true
  return document.status === 'parsed' || document.reviewStatus === 'complete'
}

async function watchUploadedDocument(
  queryClient: ReturnType<typeof useQueryClient>,
  document: HouseholdDocument,
) {
  let latest = document
  for (let attempt = 0; attempt < DOCUMENT_REVIEW_POLL_ATTEMPTS; attempt += 1) {
    if (documentApplicationDone(latest)) {
      await refreshHouseholdQueries(queryClient)
      return latest
    }

    await wait(DOCUMENT_REVIEW_POLL_INTERVAL_MS)
    const documents = await fetchHouseholdDocuments()
    queryClient.setQueryData(['household', 'documents'], documents)
    latest =
      documents.items.find((candidate) => candidate.id === document.id) ??
      latest
    await refreshHouseholdQueries(queryClient)
  }
  await refreshHouseholdQueries(queryClient)
  return latest
}

export function useHouseholdDashboard() {
  return useQuery({
    queryKey: ['household', 'dashboard'],
    queryFn: ({ signal }) => fetchHouseholdDashboard({ signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useHouseholdDocuments() {
  return useQuery({
    queryKey: ['household', 'documents'],
    queryFn: ({ signal }) => fetchHouseholdDocuments({ signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useHouseholdFacts() {
  return useQuery({
    queryKey: ['household', 'facts'],
    queryFn: fetchConfirmedFacts,
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useHouseholdLedger(params?: {
  window?: string
  kind?: string
  limit?: number
}) {
  return useQuery({
    queryKey: ['household', 'ledger', params ?? {}],
    queryFn: ({ signal }) => fetchHouseholdLedger(params, { signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useHouseholdSpending(params?: { window?: string }) {
  return useQuery({
    queryKey: ['household', 'spending', params ?? {}],
    queryFn: ({ signal }) => fetchHouseholdSpending(params, { signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useHouseholdNetWorthTrend(params?: { days?: number }) {
  return useQuery({
    queryKey: ['household', 'net-worth-trend', params ?? {}],
    queryFn: ({ signal }) => fetchHouseholdNetWorthTrend(params, { signal }),
    staleTime: HOUSEHOLD_MARKET_VALUE_REFRESH_MS,
    refetchInterval: HOUSEHOLD_MARKET_VALUE_REFRESH_MS,
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
      if (
        document.metadata?.duplicate_detected === true &&
        document.metadata?.duplicate_rebound !== true
      ) {
        toast.info(`${document.filename} already exists in evidence intake.`)
        return
      }
      toast.success(
        document.metadata?.duplicate_rebound === true
          ? `${document.filename} already exists; reapplying to selected account.`
          : `${document.filename} staged for evidence intake.`,
      )
      void watchUploadedDocument(queryClient, document)
        .then((latest) => {
          if (latest.status === 'failed' || latest.reviewStatus === 'failed') {
            toast.error(`${latest.filename} evidence review failed.`)
            return
          }
          if (applicationStatus(latest) === 'applied') {
            toast.success(`${latest.filename} applied to money views.`)
          }
        })
        .catch(() => {
          void refreshHouseholdQueries(queryClient)
        })
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to upload document',
      )
    },
  })
}

export function useUploadHouseholdDocuments() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payloads: HouseholdDocumentUpload[]) =>
      uploadHouseholdDocuments(payloads),
    onSuccess: async (documents) => {
      await refreshHouseholdQueries(queryClient)
      const staged = documents.filter(
        (document) =>
          document.metadata?.duplicate_detected !== true ||
          document.metadata?.duplicate_rebound === true,
      )
      if (staged.length === 0) {
        toast.info('Evidence files already exist in intake.')
        return
      }
      toast.success(
        `${staged.length} evidence file${staged.length === 1 ? '' : 's'} staged for intake.`,
      )
      for (const document of staged) {
        void watchUploadedDocument(queryClient, document)
          .then((latest) => {
            if (
              latest.status === 'failed' ||
              latest.reviewStatus === 'failed'
            ) {
              toast.error(`${latest.filename} evidence review failed.`)
              return
            }
            if (applicationStatus(latest) === 'applied') {
              toast.success(`${latest.filename} applied to money views.`)
            }
          })
          .catch(() => {
            void refreshHouseholdQueries(queryClient)
          })
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to upload documents',
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
      toast.success('Account saved.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to save account',
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
      toast.success('Account updated.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to update account',
      )
    },
  })
}

export function useDeleteHouseholdDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (documentId: string) => deleteHouseholdDocument(documentId),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Evidence document removed.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to remove evidence document',
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
      toast.success('Account display settings removed.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to remove account display settings',
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
