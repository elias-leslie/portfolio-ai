// SummitFlow API configuration
// Returns the SummitFlow project API URL based on current environment
export function getSummitFlowProjectApiUrl(): string {
  // Check environment variable first
  const envUrl = process.env.NEXT_PUBLIC_SUMMITFLOW_API
  if (envUrl) return envUrl

  // Runtime detection
  if (typeof window === 'undefined') {
    return 'http://localhost:8001/api/projects/portfolio-ai'
  }

  const host = window.location.hostname
  if (host === 'localhost' || host === '127.0.0.1') {
    return 'http://localhost:8001/api/projects/portfolio-ai'
  }

  // Production: use SummitFlow API domain
  if (host === 'port.summitflow.dev') {
    return 'https://devapi.summitflow.dev/api/projects/portfolio-ai'
  }

  // Fallback
  return 'http://localhost:8001/api/projects/portfolio-ai'
}

// For backwards compatibility - callers should migrate to the function
export const SUMMITFLOW_API =
  typeof window !== 'undefined'
    ? getSummitFlowProjectApiUrl()
    : 'http://localhost:8001/api/projects/portfolio-ai'
