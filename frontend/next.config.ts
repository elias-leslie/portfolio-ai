import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  transpilePackages: ['@agent-hub/passport-client', '@agent-hub/chat-ui'],
  // Don't redirect trailing slashes - let FastAPI middleware normalize them
  skipTrailingSlashRedirect: true,
  // API routing via Next.js rewrites for CF Access compatibility
  // All /api/* requests are proxied to the backend on localhost,
  // keeping everything same-origin to avoid CORS issues with CF Access cookies
  async rewrites() {
    return {
      beforeFiles: [
        // Agent Hub API proxy — enables @agent-hub/chat-ui to reach Agent Hub backend
        {
          source: '/agent-hub-api/:path*',
          destination: 'http://localhost:8003/api/:path*',
        },
      ],
      afterFiles: [
        {
          source: '/api/:path*',
          destination: 'http://localhost:8000/api/:path*',
        },
        {
          source: '/ws/:path*',
          destination: 'http://localhost:8000/ws/:path*',
        },
      ],
    }
  },
}

export default nextConfig
