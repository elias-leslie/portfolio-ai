"use client";

import { Suspense } from "react";
import { MarketConditions } from "@/components/portfolio/MarketConditions";
import { PortfolioOverview } from "@/components/portfolio/PortfolioOverview";
import { MarketNewsCard } from "@/components/dashboard/MarketNewsCard";
import { Card } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

function LoadingSkeleton({ title }: { title: string }) {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <Loader2 className="h-5 w-5 animate-spin text-accent" />
        <h3 className="text-sm font-semibold text-text">{title}</h3>
      </div>
      <div className="h-32 animate-pulse rounded bg-surface-muted/60" />
    </Card>
  );
}

export default function Dashboard() {
  return (
    <div className="bg-bg">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
            Portfolio AI Dashboard
          </h1>
          <p className="mt-3 text-base text-text-muted">
            AI-powered portfolio intelligence and market insights
          </p>
        </div>

        {/* Market Conditions */}
        <div className="mb-10">
          <Suspense fallback={<LoadingSkeleton title="Market Conditions" />}>
            <MarketConditions />
          </Suspense>
        </div>

        {/* Market News */}
        <div className="mb-10">
          <Suspense fallback={<LoadingSkeleton title="Market News" />}>
            <MarketNewsCard />
          </Suspense>
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
