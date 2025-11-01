import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow dev access from network IPs and Tailscale
  allowedDevOrigins: ["192.168.8.233:3000", "100.123.190.81:3000"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
