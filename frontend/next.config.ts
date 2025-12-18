import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Don't redirect trailing slashes - let FastAPI middleware normalize them
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // Use 127.0.0.1 instead of localhost to avoid IPv6 issues
    // Backend TrailingSlashMiddleware handles slash normalization
    return [
      // Health endpoints (not under /api prefix on backend)
      {
        source: "/health",
        destination: "http://127.0.0.1:8000/health",
      },
      {
        source: "/health/:path*",
        destination: "http://127.0.0.1:8000/health/:path*",
      },
      // Dev Companion (Agent Hub backend) - port 9999
      {
        source: "/dev-companion",
        destination: "http://127.0.0.1:9999",
      },
      {
        source: "/dev-companion/:path*",
        destination: "http://127.0.0.1:9999/:path*",
      },
      // General catch-all for all API routes
      // Backend middleware normalizes trailing slashes
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
      // SummitFlow API (port 8001) - capabilities, evidence, vision
      {
        source: "/summitflow/:path*",
        destination: "http://127.0.0.1:8001/:path*",
      },
    ];
  },
};

export default nextConfig;
