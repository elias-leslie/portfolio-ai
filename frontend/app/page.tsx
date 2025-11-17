"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { MarketIntelligence } from "@/components/market/MarketIntelligence";
import { UnifiedNewsIntelligenceCard } from "@/components/shared/UnifiedNewsIntelligenceCard";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { useNewsIntelligence } from "@/lib/hooks/useNews";
import { Loader2 } from "lucide-react";

function SectionContentSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-4">
      {[...Array(rows)].map((_, index) => (
        <div
          key={`section-skeleton-${index}`}
          className="h-16 w-full animate-pulse rounded-xl bg-surface-muted/50"
        />
      ))}
    </div>
  );
}

function SectionLoadingState({
  label,
  rows = 3,
}: {
  label: string;
  rows?: number;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-text-muted">
        <Loader2 className="h-4 w-4 animate-spin text-accent" />
        {label}
      </div>
      <SectionContentSkeleton rows={rows} />
    </div>
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
    refetch,
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
      <SectionCard
        variant="surface"
        title="Market News"
        description="Curated macro headlines and sentiment shifts across your tracked universe."
      >
        {showSkeleton && <SectionLoadingState label="Fetching latest headlines" rows={4} />}
        {!showSkeleton && error && (
          <div className="rounded-lg border border-border/50 bg-surface-muted/40 p-4 text-sm text-text-muted">
            Failed to load market news.{" "}
            <button
              className="text-primary underline-offset-2 hover:underline"
              onClick={() => refetch()}
              type="button"
            >
              Retry
            </button>
          </div>
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
      </SectionCard>
    </div>
  );
}

export default function Dashboard() {
  return (
    <div className="bg-bg">
      <div className="mx-auto max-w-7xl space-y-10 px-4 py-10 sm:px-6 lg:px-8">
        <PageHeader
          title="Portfolio AI Dashboard"
          description="AI-powered portfolio intelligence and market insights"
        />

        <SectionCard
          variant="surface"
          title="Market Intelligence"
          description="Daily macro trends, sentiment shifts, and flow signals across sectors."
        >
          <Suspense fallback={<SectionLoadingState label="Loading market intelligence" rows={5} />}>
            <MarketIntelligence />
          </Suspense>
        </SectionCard>

        <MarketNewsSection />

        {/* Portfolio Overview re-enabled once analytics.concentration issue is resolved */}
        {/* <SectionCard
          variant="surface"
          title="Portfolio Overview"
          description="Snapshot of current allocation, risk profile, and performance."
        >
          <PortfolioOverview />
        </SectionCard> */}
      </div>
    </div>
  );
}
