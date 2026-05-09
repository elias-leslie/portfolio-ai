/**
 * Drift / IPS API client. Thin pass-through over the canonical
 * /api/portfolio/ips/* contracts; no client-side analytics.
 */

import { get, put } from './client'

export type IPSScope = 'household' | 'account'

export interface IPSTarget {
  schemaVersion: number
  scope: IPSScope
  scopeId: string
  assetClass: string
  targetPct: number
  driftBandPct: number
  notes: string | null
}

export interface DriftRow {
  schemaVersion: number
  assetClass: string
  targetPct: number
  actualPct: number
  driftPct: number
  driftBandPct: number
  outOfBand: boolean
  targetValue: number
  actualValue: number
  driftValue: number
}

export interface DriftSummary {
  schemaVersion: number
  scope: IPSScope
  scopeId: string
  totalValue: number
  maxDriftPct: number
  classesOutOfBand: number
  snapshotDate: string
}

export interface DriftReport {
  schemaVersion: number
  scope: IPSScope
  scopeId: string
  snapshotDate: string
  totalValue: number
  rows: DriftRow[]
  classesMissingTargets: string[]
}

export async function fetchDriftSummary(
  scope: IPSScope,
  scopeId: string,
): Promise<DriftSummary> {
  return get<DriftSummary>(
    `/api/portfolio/ips/drift?scope=${encodeURIComponent(scope)}&scope_id=${encodeURIComponent(scopeId)}`,
  )
}

export async function fetchDriftReport(
  scope: IPSScope,
  scopeId: string,
): Promise<DriftReport> {
  return get<DriftReport>(
    `/api/portfolio/ips/drift?scope=${encodeURIComponent(scope)}&scope_id=${encodeURIComponent(scopeId)}&summary=false`,
  )
}

export async function fetchTargets(
  scope: IPSScope,
  scopeId: string,
): Promise<IPSTarget[]> {
  return get<IPSTarget[]>(
    `/api/portfolio/ips/targets?scope=${encodeURIComponent(scope)}&scope_id=${encodeURIComponent(scopeId)}`,
  )
}

export interface UpsertTargetRequest {
  scope: IPSScope
  scopeId: string
  assetClass: string
  targetPct: number
  driftBandPct?: number
  notes?: string | null
}

export async function upsertTarget(
  req: UpsertTargetRequest,
): Promise<IPSTarget> {
  return put<IPSTarget>('/api/portfolio/ips/targets', req)
}
