'use client'

import type { Dispatch, SetStateAction } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import type { ChatMessage, ContentBlock, EvidenceData } from '../wsHandlers'

// Session type
export interface Session {
  id: string
  workingDir: string
  createdAt: string
  updatedAt: string
  isActive: boolean
  metadata: Record<string, unknown>
  originalProvider?: string | null
  messageCount?: number
  description?: string | null
  participants?: string[]
}

export interface UseSessionManagementOptions {
  serverUrl: string | null
  open: boolean
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  setCurrentResponse: Dispatch<SetStateAction<ContentBlock[]>>
  setIsLoading: Dispatch<SetStateAction<boolean>>
}

export interface UseSessionManagementReturn {
  sessions: Session[]
  currentSessionId: string | null
  setCurrentSessionId: Dispatch<SetStateAction<string | null>>
  currentSession: Session | undefined
  isLoadingSessions: boolean
  fetchSessions: () => Promise<void>
  createSession: () => Promise<void>
  deleteSession: (sessionId: string) => Promise<void>
  saveEvidenceToServer: (
    sessionId: string,
    evidenceMsg: ChatMessage,
  ) => Promise<void>
}

export function useSessionManagement({
  serverUrl,
  open,
  setMessages,
  setCurrentResponse,
  setIsLoading,
}: UseSessionManagementOptions): UseSessionManagementReturn {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [isLoadingSessions, setIsLoadingSessions] = useState(true)

  const currentSession = useMemo(
    () => sessions.find((s) => s.id === currentSessionId),
    [sessions, currentSessionId],
  )

  // Fetch sessions
  const fetchSessions = useCallback(async () => {
    if (!serverUrl) return
    try {
      const response = await fetch(`${serverUrl}/sessions`)
      if (!response.ok) throw new Error('Failed to fetch sessions')
      const data = await response.json()
      setSessions(data)
      if (data.length > 0 && !currentSessionId) {
        setCurrentSessionId(data[0].id)
      }
    } catch {
      // Error handling is done by the caller
    } finally {
      setIsLoadingSessions(false)
    }
  }, [serverUrl, currentSessionId])

  useEffect(() => {
    if (serverUrl && open) {
      fetchSessions()
    }
  }, [serverUrl, open, fetchSessions])

  // Save evidence message to server
  const saveEvidenceToServer = useCallback(
    async (sessionId: string, evidenceMsg: ChatMessage) => {
      if (!sessionId || !serverUrl) return
      try {
        await fetch(`${serverUrl}/sessions/${sessionId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            role: 'evidence',
            content: evidenceMsg.content,
            metadata: { evidence: evidenceMsg.evidence },
          }),
        })
      } catch (err) {
        console.error('Failed to save evidence to server:', err)
      }
    },
    [serverUrl],
  )

  // Load history when session changes
  useEffect(() => {
    if (!serverUrl || !currentSessionId) return

    const loadHistory = async () => {
      try {
        const res = await fetch(
          `${serverUrl}/sessions/${currentSessionId}/history`,
        )
        if (res.ok) {
          const data = await res.json()
          const loadedMessages: ChatMessage[] = data.messages.map(
            (msg: {
              role: string
              content: string
              createdAt: string
              agent?: string
              metadata?: { evidence?: EvidenceData }
            }) => ({
              role: msg.role as 'user' | 'assistant' | 'system' | 'evidence',
              content: msg.content,
              timestamp: new Date(msg.createdAt),
              agent: msg.agent as 'claude' | 'gemini' | undefined,
              evidence: msg.metadata?.evidence,
            }),
          )

          setMessages(loadedMessages)
        }
      } catch (err) {
        console.error('Failed to load history:', err)
      }
    }

    setMessages([])
    setCurrentResponse([])
    setIsLoading(false)
    loadHistory()
  }, [
    currentSessionId,
    serverUrl,
    setMessages,
    setCurrentResponse,
    setIsLoading,
  ])

  // Create session
  const createSession = useCallback(async () => {
    if (!serverUrl) return
    try {
      const response = await fetch(`${serverUrl}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workingDir: '/home/kasadis/portfolio-ai',
        }),
      })
      if (!response.ok) throw new Error('Failed to create session')
      const session = await response.json()
      setSessions((prev) => [session, ...prev])
      setCurrentSessionId(session.id)
    } catch (err) {
      console.error('Failed to create session:', err)
    }
  }, [serverUrl])

  // Delete session
  const deleteSession = useCallback(
    async (sessionId: string) => {
      if (!serverUrl) return
      try {
        const response = await fetch(`${serverUrl}/sessions/${sessionId}`, {
          method: 'DELETE',
        })
        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`)
        }
        // Clear chat if deleting current session BEFORE updating session ID
        if (currentSessionId === sessionId) {
          setMessages([])
          setCurrentResponse([])
        }
        // Only update local state after confirmed deletion
        setSessions((prev) => prev.filter((s) => s.id !== sessionId))
        if (currentSessionId === sessionId) {
          setCurrentSessionId(
            sessions.find((s) => s.id !== sessionId)?.id || null,
          )
        }
      } catch (err) {
        console.error('Failed to delete session:', err)
        toast.error('Failed to delete session')
      }
    },
    [serverUrl, currentSessionId, sessions, setMessages, setCurrentResponse],
  )

  return {
    sessions,
    currentSessionId,
    setCurrentSessionId,
    currentSession,
    isLoadingSessions,
    fetchSessions,
    createSession,
    deleteSession,
    saveEvidenceToServer,
  }
}
