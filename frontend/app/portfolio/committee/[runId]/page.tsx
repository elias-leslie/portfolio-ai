'use client'

import { useRouter } from 'next/navigation'
import { use, useState } from 'react'
import { toast } from 'sonner'
import { AnalystColumn } from '@/components/committee/AnalystColumn'
import { ChatComposer } from '@/components/committee/ChatComposer'
import { DebatePane } from '@/components/committee/DebatePane'
import { IpsCheckList } from '@/components/committee/IpsCheckList'
import { KpiStrip } from '@/components/committee/KpiStrip'
import { PipelineDag } from '@/components/committee/PipelineDag'
import { RiskVoteList } from '@/components/committee/RiskVoteList'
import { VerdictBar } from '@/components/committee/VerdictBar'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { useCommitteeStream } from '@/hooks/useCommitteeStream'

export default function CommitteeRunPage({
  params,
}: {
  params: Promise<{ runId: string }>
}) {
  const { runId } = use(params)
  const router = useRouter()
  const {
    state,
    connection,
    sendFeedback,
    approve,
    abort,
    pause,
    resume,
    retro,
  } = useCommitteeStream(runId)
  const [approving, setApproving] = useState(false)

  const handleApprove = async () => {
    setApproving(true)
    try {
      await approve()
      toast.success('Paper trade executed')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Approve failed'
      toast.error(msg)
    } finally {
      setApproving(false)
    }
  }

  const handleRetro = async () => {
    try {
      const newRunId = await retro()
      if (newRunId) {
        toast.info('Retro run started')
        router.push(`/portfolio/committee/${newRunId}`)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Retro failed'
      toast.error(msg)
    }
  }

  return (
    <PageContainer className="space-y-4 py-5">
      <PageHeader
        title={state.symbol ?? 'Committee'}
        description={`Trading Floor Console · ${state.graph_version ?? 'committee'} · stream ${connection}`}
        eyebrow="Investment Committee"
        variant="gradient"
      />

      <SectionCard variant="surface" title="Pipeline" padding="sm">
        <div className="space-y-3">
          <PipelineDag state={state} />
          <KpiStrip state={state} />
        </div>
      </SectionCard>

      <div className="grid gap-4 lg:grid-cols-[1.4fr,1fr]">
        <div className="space-y-4">
          <SectionCard variant="surface" title="Analysts" padding="sm">
            <AnalystColumn agents={state.agents} />
          </SectionCard>

          <SectionCard
            variant="surface"
            title="Bull vs Bear debate"
            padding="sm"
          >
            <DebatePane state={state} />
          </SectionCard>

          <VerdictBar
            state={state}
            onApprove={handleApprove}
            onAbort={() => {
              abort().catch(() => {})
            }}
            onPause={() => {
              pause().catch(() => {})
            }}
            onResume={() => {
              resume().catch(() => {})
            }}
            onRetro={handleRetro}
            approving={approving}
          />
        </div>

        <div className="space-y-4">
          <SectionCard variant="surface" title="IPS checks" padding="sm">
            <IpsCheckList state={state} />
          </SectionCard>

          <SectionCard variant="surface" title="Risk vote" padding="sm">
            <RiskVoteList state={state} />
          </SectionCard>

          <SectionCard variant="surface" title="Feedback" padding="sm">
            <ChatComposer state={state} onSubmit={sendFeedback} />
          </SectionCard>

          {state.error ? (
            <div className="rounded-2xl border border-loss/40 bg-loss/10 p-3 text-sm text-loss-strong">
              {state.error}
            </div>
          ) : null}
        </div>
      </div>
    </PageContainer>
  )
}
