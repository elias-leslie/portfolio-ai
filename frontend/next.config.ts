import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // Use 127.0.0.1 instead of localhost to avoid IPv6 issues
    // Next.js server will proxy requests to the backend
    // Note: We handle both with and without trailing slashes to avoid FastAPI redirects
    return [
      // Routes that need trailing slash (list endpoints)
      {
        source: "/api/capabilities/features",
        destination: "http://127.0.0.1:8000/api/capabilities/features/",
      },
      {
        source: "/api/capabilities/features/summary",
        destination: "http://127.0.0.1:8000/api/capabilities/features/summary",
      },
      // Vision goals endpoints (need trailing slash)
      {
        source: "/api/vision-goals",
        destination: "http://127.0.0.1:8000/api/vision-goals/",
      },
      {
        source: "/api/vision-goals/:code",
        destination: "http://127.0.0.1:8000/api/vision-goals/:code",
      },
      {
        source: "/api/vision-goals/:code/details",
        destination: "http://127.0.0.1:8000/api/vision-goals/:code/details",
      },
      // Vision content endpoints (need trailing slash for root)
      {
        source: "/api/vision",
        destination: "http://127.0.0.1:8000/api/vision/",
      },
      {
        source: "/api/vision/",
        destination: "http://127.0.0.1:8000/api/vision/",
      },
      {
        source: "/api/vision/:path*",
        destination: "http://127.0.0.1:8000/api/vision/:path*",
      },
      // General catch-all for all other API routes
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
