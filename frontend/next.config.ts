import path from "path";
import { fileURLToPath } from "url";
import type { NextConfig } from "next";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  transpilePackages: ["@agent-hub/passport-client"],
  webpack: (config) => {
    config.resolve.alias["@agent-hub/passport-client"] = path.resolve(
      __dirname,
      "../../agent-hub/packages/passport-client/src/index.ts",
    );
    return config;
  },
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
      // Watchlist root endpoint - explicitly add trailing slash
      // (Next.js :path* strips trailing slashes, but FastAPI expects them)
      {
        source: "/api/watchlist",
        destination: "http://127.0.0.1:8000/api/watchlist/",
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
