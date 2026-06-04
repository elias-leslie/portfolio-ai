import { apiRequest } from './client'

export interface CommitteeCostDay {
  date: string
  runCount: number
  totalTokens: number
  estCostUsd: number
}

export interface CommitteeCostResponse {
  days: CommitteeCostDay[]
}

export function fetchCommitteeCost(days = 7): Promise<CommitteeCostResponse> {
  return apiRequest<CommitteeCostResponse>(`/api/committee/cost?days=${days}`)
}
