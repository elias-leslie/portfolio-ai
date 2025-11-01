import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow dev access from network IPs and Tailscale
  allowedDevOrigins: ["192.168.8.233:3000", "100.123.190.81:3000"],
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
};

export default nextConfig;
