import type { NextConfig } from 'next'
import { PORTS } from './lib/api-config'

const allowedDevOrigins = (process.env.NEXT_ALLOWED_DEV_ORIGINS ?? '')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean)

const nextConfig: NextConfig = {
  output: 'standalone',
  ...(allowedDevOrigins.length ? { allowedDevOrigins } : {}),
  // Don't redirect trailing slashes - let FastAPI middleware normalize them
  skipTrailingSlashRedirect: true,
  // WebSocket routing still needs a rewrite because route handlers cannot proxy
  // upgrade requests. Regular /api/* and /health/* traffic uses file-based
  // route handlers so API_URL is resolved at runtime instead of build time.
  async rewrites() {
    const apiUrl = process.env.API_URL || `http://localhost:${PORTS.backend}`
    return {
      beforeFiles: [],
      afterFiles: [
        {
          source: '/ws/:path*',
          destination: `${apiUrl}/ws/:path*`,
        },
      ],
    }
  },
}

export default nextConfig
