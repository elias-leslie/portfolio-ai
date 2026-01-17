/**
 * API Sources Registry Client
 *
 * Endpoints:
 * - GET /api/sources - List all data source providers
 * - GET /api/sources/{provider} - Detailed provider info
 * - GET /api/sources/gap/{gap_id} - Find providers for a gap
 * - GET /api/sources/routing/{data_type} - Data routing recommendations
 */

import { apiRequest } from './client'

// ========================================================================
// Types
// ========================================================================

export interface SourceProvider {
  name: string
  displayName: string
  tier: 'FREE' | 'PREMIUM'
  apiKeyRequired: boolean
  priority: number
  rateLimits: {
    perMinute: number | null
    perDay: number | null
    notes?: string
  }
  capabilities: string[]
  gapCoverage: string[]
  useCases: string[]
}

export interface SourcesResponse {
  version: string
  providers: SourceProvider[]
  dataRouting: Record<string, DataRouting>
  credentials: {
    storage: string
    table: string
  }
}

export interface DataRouting {
  primary: string
  fallback1?: string
  fallback2?: string
  fallback3?: string
  notes?: string
}

export interface SourceEndpoint {
  path?: string
  method?: string
  description: string
  gapId?: string
  params?: Record<string, string>
  fieldsReturned: string[]
  example?: string
  notes?: string
}

export interface SourceDetail {
  name: string
  displayName: string
  tier: 'FREE' | 'PREMIUM'
  apiKeyRequired: boolean
  envVar?: string
  dbKey?: string
  priority: number
  rateLimits: {
    perMinute: number | null
    perDay: number | null
    notes?: string
  }
  dataDelay?: string
  capabilities: Record<string, boolean>
  endpoints: Record<string, SourceEndpoint>
  premiumOnly: string[]
  useCases: string[]
  implementationFile: string
}

export interface GapProviderEndpoint {
  endpoint: string
  path: string
  description: string
  notes?: string
}

export interface GapProvider {
  provider: string
  tier: 'FREE' | 'PREMIUM'
  priority: number
  endpoints: GapProviderEndpoint[]
}

export interface GapProvidersResponse {
  gapId: string
  providers: GapProvider[]
  message?: string
}

// ========================================================================
// API Functions
// ========================================================================

/**
 * Fetch all API source providers
 */
export async function fetchSources(): Promise<SourcesResponse> {
  return apiRequest<SourcesResponse>('/api/sources/')
}

/**
 * Fetch detailed info for a specific provider
 */
export async function fetchSourceDetail(
  provider: string,
): Promise<SourceDetail> {
  return apiRequest<SourceDetail>(`/api/sources/${provider}`)
}

/**
 * Find providers that can address a specific trading gap
 */
export async function fetchGapProviders(
  gapId: string,
): Promise<GapProvidersResponse> {
  return apiRequest<GapProvidersResponse>(`/api/sources/gap/${gapId}`)
}

/**
 * Get data routing recommendations for a data type
 */
export async function fetchDataRouting(
  dataType: string,
): Promise<{ dataType: string; routing: DataRouting }> {
  return apiRequest<{ dataType: string; routing: DataRouting }>(
    `/api/sources/routing/${dataType}`,
  )
}

/**
 * Get provider counts for all gaps (batch fetch).
 * Returns a map of gap_id -> { count, providers } for efficient inline display.
 */
export async function fetchGapProviderCounts(): Promise<
  Record<string, { count: number; tier: string }>
> {
  const sourcesData = await fetchSources()

  // Build a map of gap_id -> provider info
  const gapCounts: Record<string, { count: number; hasFree: boolean }> = {}

  for (const provider of sourcesData.providers) {
    for (const gapId of provider.gapCoverage || []) {
      if (!gapCounts[gapId]) {
        gapCounts[gapId] = { count: 0, hasFree: false }
      }
      gapCounts[gapId].count++
      if (provider.tier === 'FREE') {
        gapCounts[gapId].hasFree = true
      }
    }
  }

  // Convert to final format
  const result: Record<string, { count: number; tier: string }> = {}
  for (const [gapId, data] of Object.entries(gapCounts)) {
    result[gapId] = {
      count: data.count,
      tier: data.hasFree ? 'FREE' : 'PREMIUM',
    }
  }

  return result
}
