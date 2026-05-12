'use client'

export const dynamic = 'force-dynamic'

import { useParams, useRouter } from 'next/navigation'
import { useState } from 'react'
import { toast } from 'sonner'
import { ChatComposer } from '@/components/committee/ChatComposer'
import { CommitteeTopbar } from '@/components/committee/CommitteeTopbar'
import { DebatePane } from '@/components/committee/DebatePane'
import { ExecutionLog } from '@/components/committee/ExecutionLog'
import { IpsCheckList } from '@/components/committee/IpsCheckList'
import { KpiStrip } from '@/components/committee/KpiStrip'
import { PipelineDag } from '@/components/committee/PipelineDag'
import { VerdictBar } from '@/components/committee/VerdictBar'
import { useCommitteeStream } from '@/hooks/useCommitteeStream'

export default function CommitteeRunPage() {
  const params = useParams<{ runId: string }>()
  const router = useRouter()
  const runId = params?.runId ?? null
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
    <div className="mx-auto max-w-[1480px] space-y-3.5 px-4 py-3.5">
      <CommitteeTopbar
        state={state}
        runId={runId}
        startedAt={state.started_at}
        onPause={() => {
          pause().catch(() => {})
        }}
        onResume={() => {
          resume().catch(() => {})
        }}
        onAbort={() => {
          abort().catch(() => {})
        }}
        onApprove={handleApprove}
        approving={approving}
      />

      <PipelineDag state={state} />

      <KpiStrip state={state} />

      <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-[1.5fr_1fr]">
        <DebatePane state={state} />
        <div className="flex flex-col gap-3.5">
          <ExecutionLog state={state} />
          <IpsCheckList state={state} />
        </div>
      </div>

      <VerdictBar
        state={state}
        onApprove={handleApprove}
        onAbort={() => {
          abort().catch(() => {})
        }}
        onRetro={handleRetro}
        approving={approving}
      />

      <ChatComposer state={state} onSubmit={sendFeedback} />

      <p className="text-center font-mono text-[10px] text-text-muted/60">
        stream {connection}
      </p>

      {state.error ? (
        <div className="rounded-2xl border border-loss/40 bg-loss/10 p-3 text-sm text-loss-strong">
          {state.error}
        </div>
      ) : null}
    </div>
  )
}
