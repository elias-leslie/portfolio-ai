/**
 * API configuration for Portfolio-AI frontend.
 *
 * Provides consistent URL resolution for:
 * - Development (localhost:8000)
 * - Production (same-origin via Next.js rewrites)
 *
 * REST API calls use same-origin routing in production to avoid CF Access CORS
 * issues. Next.js rewrites proxy /api/* to the backend on localhost.
 * Direct cross-origin URLs are only used for WebSocket connections and
 * external services (voice via Agent Hub).
 */

const PORTS = { frontend: 3000, backend: 8000 }
const PROD_DOMAIN = 'port.summitflow.dev'
const PROD_API_DOMAIN = 'portapi.summitflow.dev'

/**
 * Get the base URL for Portfolio-AI backend API calls.
 *
 * In production, returns empty string (same-origin) so requests go through
 * Next.js rewrites, avoiding CF Access CORS issues.
 *
 * @returns Base URL (e.g., http://localhost:8000 for dev, empty string for prod)
 */
export function getApiBaseUrl(): string {
  // Server-side: always use localhost
  if (typeof window === 'undefined') {
    return `http://localhost:${PORTS.backend}`
  }

  const host = window.location.hostname

  // Development: localhost or 127.0.0.1
  if (host === 'localhost' || host === '127.0.0.1') {
    return `http://localhost:${PORTS.backend}`
  }

  // Production: same-origin routing via Next.js rewrites
  if (host === PROD_DOMAIN) {
    return ''
  }

  // Fallback: use localhost (shouldn't happen in normal use)
  return `http://localhost:${PORTS.backend}`
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
    return `ws://localhost:${PORTS.backend}${path}`
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname

  // Development
  if (host === 'localhost' || host === '127.0.0.1') {
    return `ws://localhost:${PORTS.backend}${path}`
  }

  // Production: same-origin WebSocket via Next.js rewrites
  if (host === PROD_DOMAIN) {
    return `${protocol}//${window.location.host}${path}`
  }

  // Fallback
  return `ws://localhost:${PORTS.backend}${path}`
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

/**
 * Get Agent Hub voice WebSocket URL (external service).
 * Returns null if not configured (feature disabled).
 *
 * Voice is provided by agent-hub, which may or may not be available.
 */
export function getVoiceWsUrl(): string | null {
  // Check if voice is configured via env var
  const voiceUrl = process.env.NEXT_PUBLIC_VOICE_URL
  if (voiceUrl) {
    return voiceUrl
  }

  // In development, try to connect to local agent-hub
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'ws://localhost:8003/api/voice/ws?user_id=portfolio_user&app=portfolio'
    }
    // Production: use agent-hub production URL
    if (host === PROD_DOMAIN) {
      return 'wss://agentapi.summitflow.dev/api/voice/ws?user_id=portfolio_user&app=portfolio'
    }
  }

  return null
}
