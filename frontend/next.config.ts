import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // Use 127.0.0.1 instead of localhost to avoid IPv6 issues
    // Next.js server will proxy requests to the backend
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
  // Turbopack config (Next.js 16+ default)
  turbopack: {},
};

export default nextConfig;
