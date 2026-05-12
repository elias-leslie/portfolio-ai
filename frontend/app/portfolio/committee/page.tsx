'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { toast } from 'sonner'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { startCommitteeRun } from '@/lib/committee/api'

export default function CommitteeLandingPage() {
  const router = useRouter()
  const [symbol, setSymbol] = useState('')
  const [starting, setStarting] = useState(false)

  const handleStart = async (event: React.FormEvent) => {
    event.preventDefault()
    const cleaned = symbol.trim().toUpperCase()
    if (!cleaned) return
    setStarting(true)
    try {
      const result = await startCommitteeRun({ symbol: cleaned })
      toast.success(`Committee run started for ${cleaned}`)
      router.push(`/portfolio/committee/${result.run_id}`)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start run'
      toast.error(message)
    } finally {
      setStarting(false)
    }
  }

  return (
    <PageContainer className="space-y-4 py-5">
      <PageHeader
        title="Investment Committee"
        eyebrow="Trading Floor"
        description="Pick a symbol. Four analysts read it, the bull and bear debate, the trader proposes, IPS checks, risk votes, and the PM decides."
        variant="gradient"
      />

      <SectionCard variant="surface" title="Start a run" padding="sm">
        <form
          onSubmit={handleStart}
          className="flex flex-col gap-3 sm:flex-row sm:items-center"
        >
          <input
            type="text"
            placeholder="Symbol (e.g. NVDA)"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="flex-1 rounded-2xl border border-border-subtle bg-surface px-3 py-2 text-sm uppercase tracking-[0.16em] text-text placeholder:text-text-muted/60 focus:outline-none focus:ring-1 focus:ring-primary/40"
            maxLength={12}
          />
          <Button type="submit" disabled={starting || !symbol.trim()}>
            {starting ? 'Starting…' : 'Start Committee'}
          </Button>
        </form>
        <p className="mt-3 text-xs text-text-muted/80">
          Each run runs in-process — no cron, no background tokens. Pause,
          resume, or abort at any stage; the run survives a page reload.
        </p>
      </SectionCard>
    </PageContainer>
  )
}
