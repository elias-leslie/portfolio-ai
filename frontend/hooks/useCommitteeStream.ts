'use client'

import { useEffect, useReducer, useRef, useState } from 'react'
import {
  abortCommitteeRun,
  approveCommitteeRun,
  fetchCommitteeRun,
  pauseCommitteeRun,
  resumeCommitteeRun,
  startRetroRun,
  submitCommitteeFeedback,
} from '@/lib/committee/api'
import type { CommitteeEvent } from '@/lib/committee/events'
import {
  type CommitteeUiState,
  INITIAL_COMMITTEE_STATE,
  reduceCommitteeEvent,
  reduceCommitteeEvents,
} from '@/lib/committee/reducer'

type Action =
  | { kind: 'seed'; events: CommitteeEvent[] }
  | { kind: 'event'; event: CommitteeEvent }
  | { kind: 'reset' }

function uiReducer(state: CommitteeUiState, action: Action): CommitteeUiState {
  switch (action.kind) {
    case 'seed':
      return reduceCommitteeEvents(INITIAL_COMMITTEE_STATE, action.events)
    case 'event':
      return reduceCommitteeEvent(state, action.event)
    case 'reset':
      return INITIAL_COMMITTEE_STATE
  }
}

export type UseCommitteeStreamResult = {
  state: CommitteeUiState
  connection: 'idle' | 'connecting' | 'open' | 'closed' | 'error'
  sendFeedback: (text: string) => Promise<void>
  approve: () => Promise<void>
  pause: () => Promise<void>
  resume: () => Promise<void>
  abort: () => Promise<void>
  retro: () => Promise<string | null>
}

export function useCommitteeStream(
  runId: string | null,
): UseCommitteeStreamResult {
  const [state, dispatch] = useReducer(uiReducer, INITIAL_COMMITTEE_STATE)
  const [connection, setConnection] =
    useState<UseCommitteeStreamResult['connection']>('idle')
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!runId) {
      dispatch({ kind: 'reset' })
      setConnection('idle')
      return
    }
    let cancelled = false
    setConnection('connecting')

    // Phase 1: snapshot for SSR + initial paint.
    fetchCommitteeRun(runId)
      .then((snapshot) => {
        if (cancelled) return
        dispatch({ kind: 'seed', events: snapshot.events })
        if (
          snapshot.run.status === 'complete' ||
          snapshot.run.status === 'approved' ||
          snapshot.run.status === 'aborted' ||
          snapshot.run.status === 'failed'
        ) {
          setConnection('closed')
          return
        }
        // Phase 2: open SSE.
        const source = new EventSource(`/api/committee/runs/${runId}/stream`)
        sourceRef.current = source
        source.onopen = () => {
          if (!cancelled) setConnection('open')
        }
        source.onerror = () => {
          if (!cancelled) setConnection('error')
        }
        source.onmessage = (e) => handleMessage(e)
        const handleMessage = (e: MessageEvent) => {
          if (cancelled || !e.data) return
          try {
            const payload = JSON.parse(e.data) as CommitteeEvent
            dispatch({ kind: 'event', event: payload })
          } catch {
            // Drop malformed payloads silently — the connection stays open.
          }
        }
      })
      .catch(() => {
        if (!cancelled) setConnection('error')
      })

    return () => {
      cancelled = true
      if (sourceRef.current) {
        sourceRef.current.close()
        sourceRef.current = null
      }
      setConnection('closed')
    }
  }, [runId])

  const sendFeedback = async (text: string) => {
    if (!runId || !text.trim()) return
    await submitCommitteeFeedback(runId, text.trim())
  }

  const approve = async () => {
    if (!runId) return
    await approveCommitteeRun(runId)
  }

  const pause = async () => {
    if (!runId) return
    await pauseCommitteeRun(runId)
  }

  const resume = async () => {
    if (!runId) return
    await resumeCommitteeRun(runId)
  }

  const abort = async () => {
    if (!runId) return
    await abortCommitteeRun(runId)
  }

  const retro = async () => {
    if (!runId) return null
    const result = await startRetroRun(runId)
    return result.run_id
  }

  return {
    state,
    connection,
    sendFeedback,
    approve,
    pause,
    resume,
    abort,
    retro,
  }
}
