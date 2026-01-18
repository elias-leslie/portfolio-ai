/**
 * Service control API client for status dashboard operations
 */

import { buildApiUrl } from '../api-config'

export interface ServiceRestartResponse {
  success: boolean
  service: string
  message: string
  timestamp: string
}

/**
 * Restart a specific service
 */
export async function restartService(
  service: string,
): Promise<ServiceRestartResponse> {
  const response = await fetch(
    buildApiUrl(`/api/status/services/${service}/restart`),
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    },
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Failed to restart ${service}`)
  }

  return response.json()
}
