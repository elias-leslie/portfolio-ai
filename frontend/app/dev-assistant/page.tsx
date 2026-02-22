'use client'

import { useCallback, useMemo, useState } from 'react'
import {
  ChatPanel as ChatPanelBase,
  type ChatStreamApiConfig,
} from '@agent-hub/chat-ui'

const AGENT_HUB_API = '/agent-hub-api'

export default function DevAssistantPage() {
  const [sessionId, setSessionId] = useState<string | undefined>(undefined)

  const handleSessionCreated = useCallback((id: string) => {
    setSessionId(id)
  }, [])

  const handleNewSession = useCallback(() => {
    setSessionId(undefined)
  }, [])

  const voiceWsUrl = useMemo(() => {
    if (typeof window === 'undefined') return undefined
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/agent-hub-api/voice/ws?user_id=portfolio_user&app=portfolio-ai&mode=transcribe`
  }, [])

  const ttsBaseUrl = useMemo(() => {
    if (typeof window === 'undefined') return ''
    return window.location.origin
  }, [])

  const apiConfig: ChatStreamApiConfig = useMemo(() => ({
    completeEndpoint: `${AGENT_HUB_API}/complete`,
    sessionsEndpoint: `${AGENT_HUB_API}/sessions`,
    preferencesEndpoint: '/api/preferences',
    projectId: 'portfolio-ai',
    memoryGroupPrefix: 'agent:',
  }), [])

  return (
    <div className="flex h-screen bg-bg">
      {/* Sidebar */}
      <div className="w-64 border-r border-border flex flex-col">
        <div className="p-4 border-b border-border">
          <h1 className="text-lg font-bold text-text">Dev Assistant</h1>
          <p className="text-xs text-text-muted">Powered by Agent Hub</p>
        </div>

        <div className="p-2">
          <button
            onClick={handleNewSession}
            className="w-full px-3 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 text-sm"
          >
            + New Session
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2 text-center text-text-muted text-sm">
          Sessions managed by Agent Hub
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-h-0">
        <ChatPanelBase
          key={sessionId ?? 'new'}
          agentSlug="dev-companion"
          sessionId={sessionId}
          workingDir="/home/kasadis/portfolio-ai"
          toolsEnabled={true}
          onSessionCreated={handleSessionCreated}
          apiConfig={apiConfig}
          voiceWsUrl={voiceWsUrl}
          ttsBaseUrl={ttsBaseUrl}
        />
      </div>
    </div>
  )
}
