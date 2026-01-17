/**
 * System resources API client
 */

import { apiRequest } from './client'

export interface DiskUsage {
  totalGb: number
  usedGb: number
  freeGb: number
  percentUsed: number
  status: 'ok' | 'warning' | 'critical'
}

export interface MemoryUsage {
  totalGb: number
  usedGb: number
  availableGb: number
  percentUsed: number
  status: 'ok' | 'warning' | 'critical'
}

export interface CpuUsage {
  percentUsed: number
  cores: number
  status: 'ok' | 'warning' | 'critical'
}

export interface DatabasePool {
  poolSize: number
  checkedOut: number
  overflow: number
  percentUsed: number
  status: 'ok' | 'warning' | 'critical'
}

export interface SystemResources {
  disk: DiskUsage
  memory: MemoryUsage
  cpu: CpuUsage
  databasePool: DatabasePool
  timestamp: string
}

export async function getSystemResources(): Promise<SystemResources> {
  return apiRequest<SystemResources>('/api/status/resources')
}
