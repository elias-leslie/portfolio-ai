/**
 * Trading Intelligence Gap Detection API Client
 *
 * Endpoints:
 * - GET /api/gaps/summary - System-wide gap summary
 * - GET /api/gaps/by-analysis - Gaps grouped by analysis type
 * - GET /api/gaps/by-symbol/:symbol - Per-symbol gap analysis
 * - GET /api/gaps/watchlist - Watchlist gaps
 * - POST /api/gaps/generate-task-list - Generate task list for gaps
 */

import { buildApiUrl } from '../api-config'

// ========================================================================
// Types
// ========================================================================

export interface GapInfo {
  gapId: string
  capability: string
  analysisType: string
  criticality: 'P0' | 'P1' | 'P2' | 'P3'
  currentState: string
  desiredState: string
  impact: string
  dataSources: Array<Record<string, unknown>>
  effort: 'LOW' | 'MEDIUM' | 'HIGH'
  blocksStrategies: string[]
  recommendation: string
  severity: 'blocking' | 'limiting' | 'optional'
}

export interface CoverageResult {
  analysisType: string
  description: string
  totalCapabilities: number
  availableCapabilities: number
  missingCapabilities: number
  coveragePct: number
  maturityLevel: number // 0-3
  gaps: GapInfo[]
}

export interface GapSummary {
  timestamp: string
  totalGaps: number
  resolvedCount: number // Gaps resolved (tracked via feature passes=true)
  p0Gaps: number
  p1Gaps: number
  p2Gaps: number
  p3Gaps: number
  analysisTypes: Record<string, CoverageResult>
  avgCoveragePct: number
  top10Priorities: GapInfo[]
  mvpRoadmap: Record<string, unknown>
}

export interface GapsByAnalysis {
  analysisTypes: Record<string, CoverageResult>
}

export interface SymbolGaps {
  symbol: string
  analysisTypes: Record<string, unknown>
}

export interface WatchlistGaps {
  watchlistSymbols: string[]
  symbolCoverage: Record<string, unknown>
  aggregateGaps: Array<{
    capability: string
    description: string
    affectedSymbols: number
    totalSymbols: number
    affectedPct: number
    symbols: string[]
  }>
}

export interface TaskListGenerated {
  gapIds: string[]
  taskFile: string
  message: string
}

// ========================================================================
// API Functions
// ========================================================================

/**
 * Fetch system-wide gap summary
 */
export async function fetchGapSummary(): Promise<GapSummary> {
  const response = await fetch(`${buildApiUrl('/api/gaps/summary')}`, {
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to fetch gap summary')
  }

  return response.json()
}

/**
 * Fetch gaps grouped by analysis type
 */
export async function fetchGapsByAnalysis(): Promise<GapsByAnalysis> {
  const response = await fetch(`${buildApiUrl('/api/gaps/by-analysis')}`, {
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to fetch gaps by analysis')
  }

  return response.json()
}

/**
 * Fetch per-symbol gap analysis
 */
export async function fetchSymbolGaps(symbol: string): Promise<SymbolGaps> {
  const response = await fetch(
    `${buildApiUrl(`/api/gaps/by-symbol/${symbol}`)}`,
    {
      headers: {
        'Content-Type': 'application/json',
      },
    },
  )

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to fetch symbol gaps')
  }

  return response.json()
}

/**
 * Fetch gaps affecting current watchlist
 */
export async function fetchWatchlistGaps(): Promise<WatchlistGaps> {
  const response = await fetch(`${buildApiUrl('/api/gaps/watchlist')}`, {
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to fetch watchlist gaps')
  }

  return response.json()
}

/**
 * Generate task list to fill specific gaps
 */
export async function generateTaskList(
  gapIds: string[],
): Promise<TaskListGenerated> {
  const response = await fetch(
    `${buildApiUrl('/api/gaps/generate-task-list')}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ gap_ids: gapIds }),
    },
  )

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to generate task list')
  }

  return response.json()
}
