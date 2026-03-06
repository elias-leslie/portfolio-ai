/**
 * Unified API client with retry logic and error handling
 */

import { toCamelCaseKeys, toSnakeCaseKeys } from 'es-toolkit'
import { getApiBaseUrl as getBaseUrl } from '../api-config'

/**
 * Re-export transformation utilities for WebSocket and other non-REST use cases
 */
export { toCamelCaseKeys, toSnakeCaseKeys }

/**
 * Get the API base URL from centralized config.
 * Uses window.location to determine dev vs prod environment.
 */
function getApiBaseUrl(): string {
  return getBaseUrl()
}

/**
 * Custom API error class with status code
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public response?: Response,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/**
 * Sleep helper for retry backoff
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function hasJsonBody(response: Response): boolean {
  if (response.status === 204 || response.status === 205) {
    return false
  }

  const contentLength = response.headers.get('content-length')
  if (contentLength === '0') {
    return false
  }

  const contentType = response.headers.get('content-type')
  return contentType?.includes('application/json') ?? false
}

/**
 * Unified API request function with retry logic and error handling
 *
 * @param url - Full URL or path (will be prefixed with detected API base URL if relative)
 * @param options - Fetch options
 * @param retries - Number of retry attempts (default: 3)
 * @returns Parsed JSON response
 * @throws ApiError on failure after retries
 */
export async function apiRequest<T>(
  url: string,
  options: RequestInit = {},
  retries = 3,
): Promise<T> {
  // Construct full URL if relative path provided
  // Use getApiBaseUrl() to detect the correct backend based on current access method
  const fullUrl = url.startsWith('http') ? url : `${getApiBaseUrl()}${url}`

  // Merge default headers with custom headers
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  // TODO: Add auth interceptor here when authentication is implemented
  // Example: headers["Authorization"] = `Bearer ${getAuthToken()}`;

  let lastError: Error | null = null

  // Retry loop with exponential backoff
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await fetch(fullUrl, {
        ...options,
        headers,
      })

      // Check for HTTP errors
      if (!response.ok) {
        // Try to extract error detail from response body
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`
        try {
          const errorData = await response.json()
          if (errorData.detail) {
            errorMessage = errorData.detail
          }
        } catch {
          // If JSON parsing fails, use default error message
        }

        throw new ApiError(errorMessage, response.status, response)
      }

      if (!hasJsonBody(response)) {
        return undefined as T
      }

      // Parse and transform response (snake_case → camelCase)
      const data = await response.json()
      return toCamelCaseKeys(data) as T
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))

      // Don't retry on client errors (4xx) - these won't succeed on retry
      if (
        error instanceof ApiError &&
        error.statusCode >= 400 &&
        error.statusCode < 500
      ) {
        throw error
      }

      // If we have retries left, wait before trying again
      if (attempt < retries - 1) {
        // Exponential backoff: 1s, 2s, 3s
        const backoffMs = (attempt + 1) * 1000
        await sleep(backoffMs)
      }
    }
  }

  // All retries exhausted, throw last error
  throw lastError || new Error('Request failed after retries')
}

/**
 * Convenience method for GET requests
 */
export async function get<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  return apiRequest<T>(url, { ...options, method: 'GET' })
}

/**
 * Convenience method for POST requests
 */
export async function post<T>(
  url: string,
  data?: unknown,
  options: RequestInit = {},
): Promise<T> {
  // Transform request body (camelCase → snake_case) for backend
  const transformedData = data ? toSnakeCaseKeys(data) : undefined
  return apiRequest<T>(url, {
    ...options,
    method: 'POST',
    body: transformedData ? JSON.stringify(transformedData) : undefined,
  })
}

/**
 * Convenience method for PATCH requests
 */
export async function patch<T>(
  url: string,
  data?: unknown,
  options: RequestInit = {},
): Promise<T> {
  // Transform request body (camelCase → snake_case) for backend
  const transformedData = data ? toSnakeCaseKeys(data) : undefined
  return apiRequest<T>(url, {
    ...options,
    method: 'PATCH',
    body: transformedData ? JSON.stringify(transformedData) : undefined,
  })
}

/**
 * Convenience method for PUT requests
 */
export async function put<T>(
  url: string,
  data?: unknown,
  options: RequestInit = {},
): Promise<T> {
  const transformedData = data ? toSnakeCaseKeys(data) : undefined
  return apiRequest<T>(url, {
    ...options,
    method: 'PUT',
    body: transformedData ? JSON.stringify(transformedData) : undefined,
  })
}

/**
 * Convenience method for DELETE requests
 */
export async function del<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  return apiRequest<T>(url, { ...options, method: 'DELETE' })
}
