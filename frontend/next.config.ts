import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  // Don't redirect trailing slashes - let FastAPI middleware normalize them
  skipTrailingSlashRedirect: true,
  // API routing via Next.js rewrites for CF Access compatibility
  // All /api/* requests are proxied to the backend on localhost,
  // keeping everything same-origin to avoid CORS issues with CF Access cookies
  async rewrites() {
    const apiUrl = process.env.API_URL || 'http://localhost:8000'
    return {
      afterFiles: [
        {
          source: '/api/:path*',
          destination: `${apiUrl}/api/:path*`,
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
