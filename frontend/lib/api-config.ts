/**
 * API configuration for Portfolio-AI frontend.
 *
 * Provides consistent URL resolution for:
 * - Development on localhost (direct backend access)
 * - Any deployed or LAN host (same-origin via Next.js rewrites)
 *
 * REST API calls use same-origin routing in production to avoid CF Access CORS
 * issues. Next.js rewrites proxy /api/* to the backend on localhost.
 * Direct cross-origin URLs are only used for WebSocket connections.
 */

export const PORTS = { frontend: 3000, backend: 8000 }

/**
 * Get the base URL for Portfolio-AI backend API calls.
 *
 * In the browser, any non-localhost host stays same-origin so requests flow
 * through Next.js rewrites instead of incorrectly targeting the viewer's
 * localhost environment.
 *
 * @returns Base URL (e.g., http://localhost:8000 for dev, empty string for prod)
 */
export function getApiBaseUrl(): string {
  // Server-side: use API_URL env var (set by Docker compose) or localhost fallback
  if (typeof window === 'undefined') {
    return process.env.API_URL || `http://localhost:${PORTS.backend}`
  }

  const host = window.location.hostname

  // Development: localhost or 127.0.0.1
  if (host === 'localhost' || host === '127.0.0.1') {
    return `http://localhost:${PORTS.backend}`
  }

  // Any non-local browser host should stay same-origin via rewrites.
  return ''
}

/**
 * Get WebSocket URL for a given path.
 *
 * Automatically handles ws/wss based on current protocol.
 *
 * @param path - WebSocket path (e.g., /ws/chat)
 * @returns Full WebSocket URL
 */
export function getWsUrl(path: string): string {
  if (typeof window === 'undefined') {
    const apiUrl = process.env.API_URL || `http://localhost:${PORTS.backend}`
    return apiUrl.replace(/^http/, 'ws') + path
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname

  // Development
  if (host === 'localhost' || host === '127.0.0.1') {
    return `ws://localhost:${PORTS.backend}${path}`
  }

  // Any non-local browser host should stay same-origin via rewrites.
  return `${protocol}//${window.location.host}${path}`
}

/**
 * Build a full API URL from a path.
 *
 * @param path - API path (e.g., /api/projects)
 * @returns Full URL
 */
export function buildApiUrl(path: string): string {
  return `${getApiBaseUrl()}${path}`
}

/**
 * Check if running in development mode.
 *
 * @returns true if on localhost/127.0.0.1
 */
export function isDevelopment(): boolean {
  if (typeof window === 'undefined') {
    return true // Server-side is typically dev
  }
  const host = window.location.hostname
  return host === 'localhost' || host === '127.0.0.1'
}
