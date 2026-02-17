import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  transpilePackages: ['@agent-hub/passport-client'],
  // Don't redirect trailing slashes - let FastAPI middleware normalize them
  skipTrailingSlashRedirect: true,
  // API routing via Next.js rewrites for CF Access compatibility
  // All /api/* requests are proxied to the backend on localhost,
  // keeping everything same-origin to avoid CORS issues with CF Access cookies
  async rewrites() {
    return {
      beforeFiles: [],
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
