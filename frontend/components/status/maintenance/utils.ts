import type { MaintenanceResult } from '@/lib/api/maintenance'

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Never run'
  return new Date(dateStr).toLocaleString()
}

export function formatTaskSummary(
  label: string,
  result?: MaintenanceResult | null,
): string {
  if (!result) return `${label}: —`
  const status = result.status ? result.status.replace(/_/g, ' ') : 'unknown'
  if (!result.startedAt) return `${label}: ${status}`
  const timestamp = new Date(result.startedAt).toLocaleTimeString()
  return `${label}: ${status} @ ${timestamp}`
}

export const formatDateTime = (dateStr: string | null) => {
  if (!dateStr) return 'Never'
  try {
    return new Date(dateStr).toLocaleString()
  } catch {
    return 'Invalid date'
  }
}

export const getStatusText = (status: string) => {
  switch (status) {
    case 'critical':
      return 'Critical'
    case 'warning':
      return 'Warning'
    default:
      return 'OK'
  }
}

export const API_BASE_URL = ''
