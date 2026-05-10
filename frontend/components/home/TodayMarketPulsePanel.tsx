'use client'

import { ExternalLink, TriangleAlert } from 'lucide-react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type {
  HomeTodayBriefCatalyst,
  HomeTodayBriefImpact,
  HomeTodayBriefSource,
} from '@/lib/api/home'
import { useHomeTodayBrief } from '@/lib/hooks/useHomeTodayBrief'
import { cn } from '@/lib/utils'

function directionBadge(direction: string) {
  switch (direction) {
    case 'positive':
    case 'tailwind':
    case 'constructive':
      return 'success' as const
    case 'negative':
    case 'headwind':
      return 'destructive' as const
    case 'cautious':
    case 'warning':
      return 'warning' as const
    case 'watch':
      return 'secondary' as const
    default:
      return 'outline' as const
  }
}

function confidenceLabel(confidence: string) {
  return confidence === 'high'
    ? 'High conviction'
    : confidence === 'low'
      ? 'Low conviction'
      : 'Medium conviction'
}

function directionSurfaceClasses(direction: string) {
  switch (direction) {
    case 'positive':
    case 'constructive':
    case 'tailwind':
      return 'border-gain/30 bg-gradient-to-br from-gain/12 via-surface/80 to-surface/45'
    case 'negative':
    case 'headwind':
      return 'border-loss/30 bg-gradient-to-br from-loss/12 via-surface/80 to-surface/45'
    case 'cautious':
    case 'warning':
      return 'border-warning/30 bg-gradient-to-br from-warning/12 via-surface/80 to-surface/45'
    default:
      return 'border-border/40 bg-gradient-to-br from-surface-muted/40 via-surface/75 to-surface/45'
  }
}

function directionMarkerClasses(direction: string) {
  switch (direction) {
    case 'positive':
    case 'constructive':
    case 'tailwind':
      return 'border-gain/35 bg-gain/10 text-gain'
    case 'negative':
    case 'headwind':
      return 'border-loss/35 bg-loss/10 text-loss'
    case 'cautious':
    case 'warning':
      return 'border-warning/35 bg-warning/10 text-warning'
    default:
      return 'border-border/35 bg-surface-muted/25 text-text-muted'
  }
}

function sourceTierClasses(sourceSignalTier: string | null) {
  switch (sourceSignalTier) {
    case 'primary':
      return 'border-gain/20 bg-gain/8 text-text'
    case 'secondary':
      return 'border-border/35 bg-surface/55 text-text'
    default:
      return 'border-border/30 bg-surface-muted/20 text-text'
  }
}

function RelativeLabelOrFallback({
  value,
  fallback,
}: {
  value: string | null
  fallback: string
}) {
  return value ? <RelativeTime value={value} /> : fallback
}

function ImpactCard({
  impact,
  linkedSources,
}: {
  impact: HomeTodayBriefImpact
  linkedSources: HomeTodayBriefSource[]
}) {
  return (
    <article className="rounded-2xl border border-border/35 bg-surface/55 p-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold leading-5 text-text">
            {impact.label}
          </p>
          <p className="text-[12px] leading-5 text-text-muted">
            {impact.rationale}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          <Badge
            variant={directionBadge(impact.direction)}
            className="h-5 px-2 text-[10px] uppercase tracking-[0.16em]"
          >
            {impact.direction}
          </Badge>
          <Badge
            variant="outline"
            className="h-5 px-2 text-[10px] uppercase tracking-[0.16em]"
          >
            {impact.magnitude}
          </Badge>
        </div>
      </div>
      {impact.affectedSymbols.length > 0 ? (
        <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
          {impact.affectedSymbols.join(' · ')}
        </p>
      ) : null}
      {linkedSources.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {linkedSources.slice(0, 2).map((source) => (
            <span
              key={source.id}
              className="rounded-full border border-border/30 bg-background/20 px-2 py-1 text-[10px] uppercase tracking-[0.14em] text-text-muted"
            >
              {source.label}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  )
}

function CatalystCard({
  catalyst,
  index,
  linkedSources,
}: {
  catalyst: HomeTodayBriefCatalyst
  index: number
  linkedSources: HomeTodayBriefSource[]
}) {
  return (
    <article className="rounded-2xl border border-border/35 bg-surface/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div
              className={cn(
                'flex h-6 w-6 items-center justify-center rounded-full border font-mono text-[10px] font-semibold',
                directionMarkerClasses(catalyst.direction),
              )}
            >
              {(index + 1).toString().padStart(2, '0')}
            </div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              Catalyst
            </p>
          </div>
          <h4 className="text-[15px] font-semibold leading-6 text-text">
            {catalyst.title}
          </h4>
        </div>
        <Badge
          variant={directionBadge(catalyst.direction)}
          className="h-6 px-2.5 text-[10px] uppercase tracking-[0.16em]"
        >
          {catalyst.direction.replaceAll('_', ' ')}
        </Badge>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <div className="rounded-2xl border border-border/30 bg-background/20 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            Market reaction
          </p>
          <p className="mt-1.5 text-[12px] leading-5 text-text">
            {catalyst.marketEffect}
          </p>
        </div>
        <div className="grid gap-3">
          <div className="rounded-2xl border border-border/30 bg-background/20 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              Portfolio
            </p>
            <p className="mt-1.5 text-[12px] leading-5 text-text">
              {catalyst.portfolioEffect}
            </p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-background/20 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              Money
            </p>
            <p className="mt-1.5 text-[12px] leading-5 text-text">
              {catalyst.moneyEffect}
            </p>
          </div>
        </div>
      </div>

      {linkedSources.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {linkedSources.map((source) =>
            source.url ? (
              <a
                key={source.id}
                href={source.url}
                target="_blank"
                rel="noreferrer"
                className={cn(
                  'inline-flex max-w-full items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] transition-colors hover:border-border/60 hover:text-text',
                  sourceTierClasses(source.sourceSignalTier),
                )}
              >
                <span className="max-w-[14rem] truncate">{source.label}</span>
                <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
            ) : (
              <span
                key={source.id}
                className={cn(
                  'rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.14em]',
                  sourceTierClasses(source.sourceSignalTier),
                )}
              >
                {source.label}
              </span>
            ),
          )}
        </div>
      ) : null}
    </article>
  )
}

function SourceChip({ source }: { source: HomeTodayBriefSource }) {
  const inner = (
    <>
      <span className="truncate">{source.label}</span>
      {source.publishedAt ? (
        <span className="shrink-0 text-text-muted">
          <RelativeTime value={source.publishedAt} />
        </span>
      ) : null}
      {source.url ? <ExternalLink className="h-3 w-3 shrink-0" /> : null}
    </>
  )

  if (source.url) {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noreferrer"
        className={cn(
          'inline-flex max-w-full items-center gap-2 rounded-full border px-2.5 py-1.5 text-[10px] uppercase tracking-[0.14em] transition-colors hover:border-border/60',
          sourceTierClasses(source.sourceSignalTier),
        )}
      >
        {inner}
      </a>
    )
  }

  return (
    <div
      className={cn(
        'inline-flex max-w-full items-center gap-2 rounded-full border px-2.5 py-1.5 text-[10px] uppercase tracking-[0.14em]',
        sourceTierClasses(source.sourceSignalTier),
      )}
    >
      {inner}
    </div>
  )
}

export function TodayMarketPulsePanel() {
  const { data, isLoading, error, refetch, isFetching } = useHomeTodayBrief()

  if (error) {
    return (
      <LoadErrorState
        title="Failed to load market pulse."
        detail="Retry to refresh catalysts, market reaction, and household impact."
        onRetry={() => {
          void refetch()
        }}
        isRetrying={isFetching}
      />
    )
  }

  const prioritizedSources = data
    ? [...data.sources].sort(
        (left, right) =>
          (right.decisionValueScore ?? 0) - (left.decisionValueScore ?? 0),
      )
    : []
  const visibleSources = prioritizedSources.slice(0, 6)

  return (
    <SectionCard
      variant="surface"
      title="Market Pulse"
      description={
        isLoading || !data ? (
          'Loading catalyst and market-impact brief.'
        ) : data.generatedAt ? (
          <>
            Updated <RelativeTime value={data.generatedAt} />
          </>
        ) : (
          'Update time unavailable'
        )
      }
      actions={
        !isLoading && data ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant="outline"
              className="h-6 px-2.5 text-[10px] uppercase tracking-[0.16em]"
            >
              {data.marketStatus.replaceAll('_', ' ')}
            </Badge>
            <Badge
              variant="outline"
              className="h-6 px-2.5 text-[10px] uppercase tracking-[0.16em]"
            >
              {confidenceLabel(data.brief.confidence)}
            </Badge>
          </div>
        ) : null
      }
      padding="none"
      headerClassName="px-5 py-4"
      contentClassName="overflow-hidden"
      className="h-full"
    >
      {isLoading || !data ? (
        <div
          className="grid gap-px bg-border/40 xl:grid-cols-[minmax(0,1.18fr)_minmax(20rem,0.82fr)]"
          role="status"
        >
          <div className="space-y-4 bg-surface/55 p-4">
            <div className="h-44 rounded-2xl skeleton" />
            <div className="h-64 rounded-2xl skeleton" />
          </div>
          <div className="space-y-4 bg-surface/35 p-4">
            <div className="h-48 rounded-2xl skeleton" />
            <div className="h-40 rounded-2xl skeleton" />
          </div>
        </div>
      ) : (
        <div className="grid gap-px bg-border/40 xl:grid-cols-[minmax(0,1.18fr)_minmax(20rem,0.82fr)]">
          <div className="space-y-4 bg-surface/55 p-4">
            <section
              className={cn(
                'relative overflow-hidden rounded-3xl border p-4',
                directionSurfaceClasses(data.brief.stance),
              )}
            >
              <div className="pointer-events-none absolute inset-y-0 right-0 w-40 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.14),transparent_68%)]" />
              <div className="relative space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                        Lead call
                      </p>
                      <div className="h-px w-8 bg-border/45" />
                      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                        <RelativeLabelOrFallback
                          value={data.asOf.market}
                          fallback="Market time missing"
                        />
                      </p>
                    </div>
                    <h3 className="max-w-4xl font-display text-[1.55rem] italic leading-tight tracking-tight text-text sm:text-[1.9rem]">
                      {data.brief.headline}
                    </h3>
                  </div>
                  <Badge
                    variant={directionBadge(data.brief.stance)}
                    className="h-6 px-2.5 text-[10px] uppercase tracking-[0.16em]"
                  >
                    {data.brief.stance}
                  </Badge>
                </div>

                <p className="max-w-4xl text-[13px] leading-6 text-text">
                  {data.brief.summary}
                </p>

                <div className="grid gap-3 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                  <div className="rounded-2xl border border-border/30 bg-background/20 p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                      Why now
                    </p>
                    <p className="mt-1.5 text-[12px] leading-5 text-text">
                      {data.brief.whyNow}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border/30 bg-background/20 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                        Desk notes
                      </p>
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted">
                        {data.brief.bullets.length} reads
                      </p>
                    </div>
                    <div className="mt-2 space-y-2">
                      {data.brief.bullets.slice(0, 3).map((bullet, index) => (
                        <div
                          key={bullet}
                          className="flex gap-2 rounded-2xl border border-border/25 bg-surface/25 px-2.5 py-2"
                        >
                          <span className="pt-0.5 font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                            {(index + 1).toString().padStart(2, '0')}
                          </span>
                          <p className="text-[12px] leading-5 text-text">
                            {bullet}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-border/40 bg-surface/45 p-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Catalyst tape
                  </p>
                  <h4 className="mt-1 font-display text-lg tracking-tight text-text">
                    What moved tape and why it matters
                  </h4>
                </div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                  {data.catalysts.length} active drivers
                </p>
              </div>

              <div className="mt-4 space-y-3">
                {data.catalysts.map((catalyst, index) => {
                  const linkedSources = prioritizedSources.filter((source) =>
                    catalyst.sourceIds.includes(source.id),
                  )

                  return (
                    <CatalystCard
                      key={catalyst.id}
                      catalyst={catalyst}
                      index={index}
                      linkedSources={linkedSources}
                    />
                  )
                })}
              </div>
            </section>
          </div>

          <div className="space-y-4 bg-surface/35 p-4">
            <section className="rounded-2xl border border-border/40 bg-surface/50 p-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Transmission
                  </p>
                  <h4 className="mt-1 font-display text-lg tracking-tight text-text">
                    What it means for us
                  </h4>
                </div>
                <Badge
                  variant="outline"
                  className="h-5 px-2 text-[10px] uppercase tracking-[0.16em]"
                >
                  {data.asOf.portfolio ? (
                    <>
                      Quotes <RelativeTime value={data.asOf.portfolio} />
                    </>
                  ) : (
                    'Quote time unavailable'
                  )}
                </Badge>
              </div>

              <div className="mt-4 space-y-3">
                {data.impacts.map((impact) => {
                  const linkedSources = prioritizedSources.filter((source) =>
                    impact.sourceIds.includes(source.id),
                  )

                  return (
                    <ImpactCard
                      key={impact.label}
                      impact={impact}
                      linkedSources={linkedSources}
                    />
                  )
                })}
              </div>
            </section>

            {data.stalenessNotes.length > 0 ? (
              <section className="rounded-2xl border border-warning/25 bg-warning/8 p-4">
                <div className="flex items-start gap-3">
                  <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-warning">
                      Confidence drag
                    </p>
                    <div className="mt-2 space-y-2">
                      {data.stalenessNotes.map((note) => (
                        <p
                          key={note}
                          className="text-[12px] leading-5 text-text"
                        >
                          {note}
                        </p>
                      ))}
                    </div>
                  </div>
                </div>
              </section>
            ) : null}

            <section className="rounded-2xl border border-border/40 bg-surface/50 p-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Source stack
                  </p>
                  <h4 className="mt-1 font-display text-lg tracking-tight text-text">
                    Evidence behind the read
                  </h4>
                </div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                  {prioritizedSources.length} tracked inputs
                </p>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {visibleSources.map((source) => (
                  <SourceChip key={source.id} source={source} />
                ))}
              </div>

              {prioritizedSources.length > visibleSources.length ? (
                <p className="mt-3 text-[11px] leading-5 text-text-muted">
                  +{prioritizedSources.length - visibleSources.length} more
                  tracked sources kept in rotation for the next refresh.
                </p>
              ) : null}
            </section>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
