import type { MaintenanceResult } from '@/lib/api/maintenance'

export interface TaskSectionProps {
  title: string
  description: string
  icon: React.ReactNode
  lastRun: MaintenanceResult | null
  onTrigger: () => void
  isLoading: boolean
}

export interface ActionDialogConfig {
  title: string
  description: string
  actionLabel: string
  onConfirm: () => void
  storageKey?: string
  isDestructive?: boolean
}

export interface ScheduledTask {
  name: string
  description: string
  nextRun: string
  lastRun: string | null
  schedule: string
}

export interface DiskSpaceInfo {
  path: string
  usedGb: number
  totalGb: number
  percentUsed: number
  status: 'ok' | 'warning' | 'critical'
}

export interface DatabaseSize {
  databaseName: string
  sizeMb: number
  tables: TableInfo[]
}

export interface TableInfo {
  name: string
  sizeMb: number
  rows: number
}

export interface ScheduleResponse {
  tasks: ScheduledTask[]
}

export interface DiskSpaceResponse {
  disks: DiskSpaceInfo[]
}

export interface DatabaseSizeResponse {
  database: DatabaseSize
}
