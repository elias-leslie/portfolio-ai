'use client'

import { Loader2 } from 'lucide-react'
import { Suspense, useEffect, useRef, useState } from 'react'
import { AutomationCenter } from '@/components/home/AutomationCenter'
import { MarketIntelligence } from '@/components/market/MarketIntelligence'
import { HomeActionQueue } from '@/components/home/HomeActionQueue'
import { TodayIdeasSection } from '@/components/recommendations/TodayIdeasSection'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { UnifiedNewsIntelligenceCard } from '@/components/shared/UnifiedNewsIntelligenceCard'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { useNewsIntelligence } from '@/lib/hooks/useNews'
import { PortfolioOverview } from '@/components/portfolio/PortfolioOverview'
import { SectionCard } from '@/components/shared/SectionCard'

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
  )
}

function SectionLoadingState({
  label,
  rows = 3,
}: {
  label: string
  rows?: number
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-text-muted">
        <Loader2 className="h-4 w-4 animate-spin text-accent" />
        {label}
      </div>
      <SectionContentSkeleton rows={rows} />
    </div>
  )
}

// Fetch enough articles initially for balanced view (top 3 positive + top 3 negative)
// Need ~20 to ensure we get a mix of sentiments from recent news
const MARKET_NEWS_INITIAL_LIMIT = 20
const MARKET_NEWS_EXPANDED_LIMIT = 50

function MarketNewsSection() {
  const sectionRef = useRef<HTMLDivElement | null>(null)
  const [shouldFetch, setShouldFetch] = useState(false)
  const [articleLimit, setArticleLimit] = useState(MARKET_NEWS_INITIAL_LIMIT)

  useEffect(() => {
    if (shouldFetch) {
      return
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldFetch(true)
          observer.disconnect()
        }
      },
      { threshold: 0.1, rootMargin: '300px' }, // Prefetch 300px before visible
    )

    const current = sectionRef.current
    if (current) {
      observer.observe(current)
    }

    return () => {
      observer.disconnect()
    }
  }, [shouldFetch])

  const {
    data: newsData,
    isLoading,
    error,
    isFetching,
    refetch,
  } = useNewsIntelligence(undefined, {
    limit: articleLimit,
    enabled: shouldFetch,
  })

  const handleExpandRequest = () => {
    if (articleLimit < MARKET_NEWS_EXPANDED_LIMIT) {
      setArticleLimit(MARKET_NEWS_EXPANDED_LIMIT)
    }
  }

  const showSkeleton = !shouldFetch || isLoading
  const isLoadingMore = isFetching && articleLimit > MARKET_NEWS_INITIAL_LIMIT

  return (
    <div ref={sectionRef}>
      {showSkeleton && (
        <SectionLoadingState label="Fetching latest headlines" rows={4} />
      )}
      {!showSkeleton && error && (
        <div className="rounded-lg border border-border/50 bg-surface-muted/40 p-4 text-sm text-text-muted">
          Failed to load market news.{' '}
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
          symbol={null}
          onRequestExpanded={
            articleLimit < MARKET_NEWS_EXPANDED_LIMIT
              ? handleExpandRequest
              : undefined
          }
          isLoadingMore={isLoadingMore}
        />
      )}
    </div>
  )
}

export default function Dashboard() {
  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        title="Today"
        description="What matters today: a short list of ideas, market context, and portfolio checks."
      />

      <WorkspaceTabs
        defaultValue="operate"
        tabs={[
          {
            value: 'operate',
            label: 'Operate',
            description: 'Start with the action queue, automation controls, and today’s ideas.',
            content: (
              <div className="space-y-6">
                <HomeActionQueue />
                <AutomationCenter />
                <TodayIdeasSection />
              </div>
            ),
          },
          {
            value: 'market',
            label: 'Market',
            description: 'Keep the market context and latest headlines together instead of buried lower on the page.',
            content: (
              <div className="space-y-6">
                <Suspense
                  fallback={
                    <SectionLoadingState label="Loading market intelligence" rows={5} />
                  }
                >
                  <MarketIntelligence />
                </Suspense>
                <MarketNewsSection />
              </div>
            ),
          },
          {
            value: 'portfolio',
            label: 'Portfolio',
            description: 'Use the portfolio coach when you need a concentration and sizing check.',
            content: (
              <SectionCard
                variant="surface"
                title="Portfolio Coach"
                description="A plain-English check on size, concentration, and recent performance."
              >
                <Suspense
                  fallback={<SectionLoadingState label="Loading portfolio overview" rows={4} />}
                >
                  <PortfolioOverview />
                </Suspense>
              </SectionCard>
            ),
          },
        ]}
      />
    </PageContainer>
  )
}
