import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  transpilePackages: ['@agent-hub/passport-client'],
  // Don't redirect trailing slashes - let FastAPI middleware normalize them
  skipTrailingSlashRedirect: true,
  // API routing is handled client-side via lib/api-config.ts
  // No rewrites needed - buildApiUrl() resolves to correct backend URL
  // based on window.location (localhost for dev, portapi.summitflow.dev for prod)
}

export default nextConfig
