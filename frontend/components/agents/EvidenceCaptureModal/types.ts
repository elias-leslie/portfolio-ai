export interface AcceptanceCriterion {
  id: string
  criterion: string
  verification?: string
  type: string
  passed?: boolean | null
}

export interface Feature {
  featureId: string
  name: string
  category: string
  acceptanceCriteria: AcceptanceCriterion[]
}

export interface ProcessedFeature extends Feature {
  uiCriteria: AcceptanceCriterion[]
  uiCount: number
  urlMatch: boolean
  matchingCriteriaIds: string[]
}

export interface EvidenceCaptureResult {
  success: boolean
  version: number
  featureId: string
  criterionId: string
  error?: string
  evidence?: {
    console: { errorCount: number; warningCount: number }
    network: { failedRequests: number }
    metadata: { url: string; capturedAt: string }
  }
}

export interface ClientEvidence {
  console: {
    errors: string[]
    warnings: string[]
    errorCount: number
    warningCount: number
  }
  network: {
    failures: Array<{
      url: string
      status: number
      statusText: string
    }>
    failureCount: number
  }
}

export type SortField = 'feature_id' | 'name' | 'category' | 'ui_count' | 'url_match'
export type SortDirection = 'asc' | 'desc'
export type CaptureMode = 'debug' | 'new' | 'existing'
