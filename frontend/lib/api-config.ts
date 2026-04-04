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
 * In the browser, all requests stay same-origin and flow through Next.js
 * rewrites. This keeps native and container installs aligned and avoids
 * coupling browser traffic to whichever backend port the host machine uses.
 *
 * @returns Base URL (e.g., http://localhost:8000 for dev, empty string for prod)
 */
export function getApiBaseUrl(): string {
  // Server-side: use API_URL env var (set by Docker compose) or localhost fallback
  if (typeof window === 'undefined') {
    return process.env.API_URL || `http://localhost:${PORTS.backend}`
  }

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
  return `${protocol}//${window.location.host}${path}`
}
