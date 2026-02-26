'use client'

import { useCallback } from 'react'
import type { EvidenceCaptureResult } from '../EvidenceCaptureModal'
import { SUMMITFLOW_API } from '../constants'
import type { ChatMessage, EvidenceData, PermissionRequest } from '../wsHandlers'

// Magic string constants
const EVIDENCE_CONTEXT_LIMIT = 5
const EVIDENCE_CONTEXT_SEPARATOR = '\n--- Available Evidence ---\n'
const FINANCIAL_MODE = 'financial'

interface UseAgentPanelActionsOptions {
  input: string
  setInput: (v: string) => void
  messages: ChatMessage[]
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
  isLoading: boolean
  isConnected: boolean
  agentMode: string
  agentProvider: string
  pendingPermission: PermissionRequest | null
  setPendingPermission: React.Dispatch<
    React.SetStateAction<PermissionRequest | null>
  >
  setIsLoading: React.Dispatch<React.SetStateAction<boolean>>
  wsRef: React.MutableRefObject<WebSocket | null>
  pageContext?: { path: string; data?: Record<string, unknown> }
  currentSessionId: string | null
  saveEvidenceToServer: (sessionId: string, msg: ChatMessage) => Promise<void>
}

export function useAgentPanelActions({
  input,
  setInput,
  messages,
  setMessages,
  isLoading,
  isConnected,
  agentMode,
  agentProvider,
  pendingPermission,
  setPendingPermission,
  setIsLoading,
  wsRef,
  pageContext,
  currentSessionId,
  saveEvidenceToServer,
}: UseAgentPanelActionsOptions) {
  const buildEvidenceContext = useCallback(() => {
    const evidenceMessages = messages
      .filter(
        (msg): msg is ChatMessage & { evidence: EvidenceData } =>
          msg.role === 'evidence' && !!msg.evidence,
      )
      .slice(-EVIDENCE_CONTEXT_LIMIT)

    if (evidenceMessages.length === 0) return ''

    const evidenceLines = evidenceMessages.map((msg) => {
      const e = msg.evidence
      const screenshotUrl = `${SUMMITFLOW_API}/evidence/${e.featureId}/${e.criterionId}/screenshot`
      return `[Evidence: ${e.featureId}/${e.criterionId} v${e.version} - ${e.consoleErrors} console errors, ${e.networkFailures} network failures - screenshot: ${screenshotUrl}]`
    })

    return `${EVIDENCE_CONTEXT_SEPARATOR}${evidenceLines.join('\n')}\n---\n\n`
  }, [messages])

  const sendMessage = useCallback(() => {
    console.log('sendMessage called:', {
      hasInput: !!input.trim(),
      hasWs: !!wsRef.current,
      wsState: wsRef.current?.readyState,
      isLoading,
      isConnected,
      agentProvider,
    })
    if (!input.trim() || !wsRef.current || isLoading) return

    const message = input.trim()

    let contextPrefix = ''
    if (agentMode === FINANCIAL_MODE && pageContext) {
      contextPrefix = `[Page: ${pageContext.path}]\n`
      if (pageContext.data) {
        contextPrefix += `[Context: ${JSON.stringify(pageContext.data)}]\n\n`
      }
    }

    const evidenceContext = buildEvidenceContext()

    setInput('')
    setIsLoading(true)

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: message, timestamp: new Date() },
    ])

    wsRef.current.send(
      JSON.stringify({
        type: 'message',
        content: contextPrefix + evidenceContext + message,
      }),
    )
  }, [
    input,
    setInput,
    isLoading,
    isConnected,
    agentMode,
    agentProvider,
    pageContext,
    buildEvidenceContext,
    setMessages,
    setIsLoading,
    wsRef,
  ])

  const stopResponse = useCallback(() => {
    if (!wsRef.current || !isLoading) return
    wsRef.current.send(JSON.stringify({ type: 'interrupt' }))
    setIsLoading(false)
    setPendingPermission(null)
  }, [wsRef, isLoading, setIsLoading, setPendingPermission])

  const handlePermissionResponse = useCallback(
    (allowed: boolean) => {
      if (!wsRef.current || !pendingPermission) return
      wsRef.current.send(
        JSON.stringify({ type: 'permission_response', allowed }),
      )
      setMessages((prev) => [
        ...prev,
        {
          role: 'system',
          content: `Permission ${allowed ? 'ALLOWED' : 'DENIED'} for: ${pendingPermission.toolName}`,
          timestamp: new Date(),
        },
      ])
      setPendingPermission(null)
    },
    [wsRef, pendingPermission, setMessages, setPendingPermission],
  )

  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        sendMessage()
      }
    },
    [sendMessage],
  )

  const handleEvidenceCaptured = useCallback(
    (result: EvidenceCaptureResult) => {
      const evidenceMsg: ChatMessage = {
        role: 'evidence',
        content: `Evidence captured for ${result.featureId}`,
        timestamp: new Date(),
        evidence: {
          featureId: result.featureId,
          criterionId: result.criterionId,
          version: result.version,
          consoleErrors: result.evidence?.console?.errorCount ?? 0,
          networkFailures: result.evidence?.network?.failedRequests ?? 0,
          url: result.evidence?.metadata?.url ?? '',
        },
      }
      setMessages((prev) => [...prev, evidenceMsg])
      if (currentSessionId) saveEvidenceToServer(currentSessionId, evidenceMsg)
    },
    [currentSessionId, saveEvidenceToServer, setMessages],
  )

  return {
    buildEvidenceContext,
    sendMessage,
    stopResponse,
    handlePermissionResponse,
    handleKeyPress,
    handleEvidenceCaptured,
  }
}
