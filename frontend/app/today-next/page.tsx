'use client'

export const dynamic = 'force-dynamic'

import Link from 'next/link'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { CommitteeFanOut } from '@/components/today-next/CommitteeFanOut'
import { MacroGateCard } from '@/components/today-next/MacroGateCard'
import { ScannerTable } from '@/components/today-next/ScannerTable'
import { Button } from '@/components/ui/button'
import { useTodayNext } from '@/lib/hooks/useTodayNext'

export default function TodayNextPage() {
  const { data, isLoading, error, refetch, isFetching } = useTodayNext()

  return (
    <PageContainer className="space-y-5 py-5">
      <PageHeader
        title="Today Next"
        description="Three-tier signal stack: macro gate, scanner, and committee fan-out."
        eyebrow="Signals"
        size="md"
        variant="plain"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link href="/portfolio?tab=signals">Portfolio signals</Link>
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                void refetch()
              }}
              disabled={isFetching}
            >
              {isFetching ? 'Refreshing…' : 'Refresh'}
            </Button>
          </div>
        }
      />

      <div className="info-banner flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span>3-tier stack live: macro gate, scanner, committee fan-out.</span>
        <Link
          href="/today"
          className="font-medium text-primary hover:underline"
        >
          Back to Today
        </Link>
      </div>

      {error ? (
        <div className="rounded-2xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error instanceof Error
            ? error.message
            : 'Failed to load Today Next.'}
        </div>
      ) : null}

      {isLoading ? (
        <div className="rounded-2xl border border-border-subtle bg-surface/50 p-6 text-sm text-text-muted">
          Loading signal stack…
        </div>
      ) : null}

      {data ? (
        <>
          <MacroGateCard macroGate={data.macroGate} />
          <ScannerTable candidates={data.scanner} />
          <CommitteeFanOut candidates={data.committee} />
        </>
      ) : null}
    </PageContainer>
  )
}
