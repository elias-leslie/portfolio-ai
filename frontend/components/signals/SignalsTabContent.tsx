'use client'

import { useEffect, useMemo, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { useBlendedSignals, useScannerLatest } from '@/lib/hooks/useSignals'
import { BlendWeightControl, loadStoredScannerPct } from './BlendWeightControl'
import { DeploymentZoneHero } from './DeploymentZoneHero'
import { ScannerTable } from './ScannerTable'

export function SignalsTabContent() {
  const [scannerPct, setScannerPct] = useState<number>(60)

  useEffect(() => {
    setScannerPct(loadStoredScannerPct())
  }, [])

  const weights = useMemo(() => {
    const s = scannerPct / 100
    return { weightScanner: s, weightCommittee: 1 - s }
  }, [scannerPct])

  const blended = useBlendedSignals({ limit: 100, ...weights })
  const scannerLatest = useScannerLatest(100)

  const factorPercentilesBySymbol = useMemo(() => {
    const out: Record<string, Record<string, number | null>> = {}
    for (const score of scannerLatest.data?.scores ?? []) {
      out[score.symbol] = score.percentiles
    }
    return out
  }, [scannerLatest.data])

  return (
    <div className="space-y-4">
      <DeploymentZoneHero />

      <SectionCard
        variant="surface"
        padding="md"
        title="Blended scanner"
        description={
          blended.data
            ? `${blended.data.run.scoredCount} symbols ranked from run ${blended.data.run.runDate} · gate ${blended.data.run.gateZone}`
            : 'Blending the L2 scanner with the L3 committee verdict.'
        }
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
          <div>
            {blended.error ? (
              <div className="rounded-2xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
                {blended.error instanceof Error
                  ? blended.error.message
                  : 'Failed to load blended signals.'}
              </div>
            ) : blended.isLoading ? (
              <div className="rounded-2xl border border-border-subtle bg-surface/50 px-4 py-6 text-sm text-text-muted">
                Loading blended signals…
              </div>
            ) : (
              <ScannerTable
                rows={blended.data?.rows ?? []}
                factorPercentilesBySymbol={factorPercentilesBySymbol}
              />
            )}
          </div>
          <div>
            <BlendWeightControl value={scannerPct} onChange={setScannerPct} />
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
