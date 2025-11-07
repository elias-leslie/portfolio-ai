"use client";

import { MarketConditions } from "@/components/portfolio/MarketConditions";
import { PortfolioOverview } from "@/components/portfolio/PortfolioOverview";

export default function Dashboard() {
  return (
    <div className="bg-bg">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-3xl font-semibold text-text">
            Portfolio AI Dashboard
          </h1>
          <p className="mt-2 text-sm text-text-muted">
            AI-powered portfolio intelligence and market insights
          </p>
        </div>

        {/* Market Conditions */}
        <div className="mb-10">
          <MarketConditions />
        </div>

        {/* Portfolio Overview */}
        {/* Temporarily disabled due to analytics.concentration error */}
        {/* <div className="mb-10 space-y-4">
          <h2 className="text-xl font-semibold text-text">Portfolio Overview</h2>
          <PortfolioOverview />
        </div> */}
      </div>
    </div>
  );
}
