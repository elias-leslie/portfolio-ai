"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { MarketIntelligence } from "@/components/market/MarketIntelligence";
import { PortfolioOverview } from "@/components/portfolio/PortfolioOverview";
import { UnifiedNewsIntelligenceCard } from "@/components/shared/UnifiedNewsIntelligenceCard";
import { useNewsIntelligence } from "@/lib/hooks/useNews";
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

const MARKET_NEWS_INITIAL_LIMIT = 6;
const MARKET_NEWS_EXPANDED_LIMIT = 50;

function MarketNewsSection() {
  const sectionRef = useRef<HTMLDivElement | null>(null);
  const [shouldFetch, setShouldFetch] = useState(false);
  const [articleLimit, setArticleLimit] = useState(MARKET_NEWS_INITIAL_LIMIT);

  useEffect(() => {
    if (shouldFetch) {
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldFetch(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15 }
    );

    const current = sectionRef.current;
    if (current) {
      observer.observe(current);
    }

    return () => {
      observer.disconnect();
    };
  }, [shouldFetch]);

  const {
    data: newsData,
    isLoading,
    error,
    isFetching,
  } = useNewsIntelligence(undefined, {
    limit: articleLimit,
    enabled: shouldFetch,
  });

  const handleExpandRequest = () => {
    if (articleLimit < MARKET_NEWS_EXPANDED_LIMIT) {
      setArticleLimit(MARKET_NEWS_EXPANDED_LIMIT);
    }
  };

  const showSkeleton = !shouldFetch || isLoading;
  const isLoadingMore = isFetching && articleLimit > MARKET_NEWS_INITIAL_LIMIT;

  return (
    <div ref={sectionRef}>
      {showSkeleton && <LoadingSkeleton title="Market News" />}
      {!showSkeleton && error && (
        <Card className="p-6">
          <div className="text-sm text-text-muted py-4">Failed to load market news</div>
        </Card>
      )}
      {!showSkeleton && !error && (
        <UnifiedNewsIntelligenceCard
          marketNewsData={newsData}
          ticker={null}
          showHeader={false}
          onRequestExpanded={
            articleLimit < MARKET_NEWS_EXPANDED_LIMIT ? handleExpandRequest : undefined
          }
          isLoadingMore={isLoadingMore}
        />
      )}
    </div>
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

        {/* Market Intelligence */}
        <div className="mb-10">
          <Suspense fallback={<LoadingSkeleton title="Market Intelligence" />}>
            <MarketIntelligence />
          </Suspense>
        </div>

        {/* Market News */}
        <div className="mb-10">
          <MarketNewsSection />
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
