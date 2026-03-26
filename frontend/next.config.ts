import type { NextConfig } from 'next'
import { PORTS } from './lib/api-config'

const SUMMITFLOW_API_URL = process.env.SUMMITFLOW_API_URL || 'http://localhost:8001'

const nextConfig: NextConfig = {
  output: 'standalone',
  transpilePackages: ['@summitflow/notes-ui'],
  // Don't redirect trailing slashes - let FastAPI middleware normalize them
  skipTrailingSlashRedirect: true,
  // API routing via Next.js rewrites for CF Access compatibility
  // All /api/* requests are proxied to the backend on localhost,
  // keeping everything same-origin to avoid CORS issues with CF Access cookies
  async rewrites() {
    const apiUrl = process.env.API_URL || `http://localhost:${PORTS.backend}`
    return {
      beforeFiles: [
        // Notes API → SummitFlow backend (centralized notes service)
        {
          source: '/api/notes/:path*',
          destination: `${SUMMITFLOW_API_URL}/api/notes/:path*`,
        },
        {
          source: '/api/notes',
          destination: `${SUMMITFLOW_API_URL}/api/notes`,
        },
      ],
      afterFiles: [
        {
          source: '/api/:path*',
          destination: `${apiUrl}/api/:path*`,
        },
        {
          source: '/health/:path*',
          destination: `${apiUrl}/health/:path*`,
        },
        {
          source: '/ws/:path*',
          destination: `${apiUrl}/ws/:path*`,
        },
      ],
    }
  },
}

export default nextConfig
