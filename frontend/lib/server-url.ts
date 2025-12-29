/**
 * Server URL utilities for connecting to dev-companion and other backend services.
 */

/**
 * Get the server URL based on current hostname.
 *
 * Uses environment variable if available, otherwise constructs URL from window.location
 * using the nginx proxy path for SSL termination.
 *
 * @returns Server URL string, or null if called on server side
 */
export function getServerUrl(): string | null {
  if (typeof window === 'undefined') return null;

  if (process.env.NEXT_PUBLIC_DEV_COMPANION_URL) {
    return process.env.NEXT_PUBLIC_DEV_COMPANION_URL;
  }

  // Use proxied path through nginx (handles SSL)
  return `${window.location.origin}/dev-companion`;
}

/**
 * Get WebSocket URL from server URL.
 *
 * Converts http(s) to ws(s) protocol.
 *
 * @param serverUrl - The HTTP server URL
 * @returns WebSocket URL string
 */
export function getWsUrl(serverUrl: string): string {
  return serverUrl.replace(/^http/, 'ws');
}
