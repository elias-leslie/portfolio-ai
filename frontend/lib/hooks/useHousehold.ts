import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  answerHouseholdQuestion,
  type HouseholdDocumentUpload,
  type HouseholdProfileUpdate,
  fetchHouseholdDashboard,
  fetchHouseholdDocuments,
  fetchHouseholdProfile,
  fetchHouseholdQuestions,
  updateHouseholdProfile,
  uploadHouseholdDocument,
} from '@/lib/api/household'

export function useHouseholdDashboard() {
  return useQuery({
    queryKey: ['household', 'dashboard'],
    queryFn: fetchHouseholdDashboard,
    staleTime: 1000 * 60,
  })
}

export function useHouseholdProfile() {
  return useQuery({
    queryKey: ['household', 'profile'],
    queryFn: fetchHouseholdProfile,
    staleTime: 1000 * 60,
  })
}

export function useHouseholdDocuments() {
  return useQuery({
    queryKey: ['household', 'documents'],
    queryFn: fetchHouseholdDocuments,
    staleTime: 1000 * 30,
  })
}

export function useHouseholdQuestions() {
  return useQuery({
    queryKey: ['household', 'questions'],
    queryFn: fetchHouseholdQuestions,
    staleTime: 1000 * 30,
  })
}

export function useUpdateHouseholdProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdProfileUpdate) => updateHouseholdProfile(payload),
    onSuccess: (profile) => {
      queryClient.setQueryData(['household', 'profile'], profile)
      queryClient.invalidateQueries({ queryKey: ['household'], refetchType: 'active' })
      toast.success('Household plan updated.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to update household plan')
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
