'use client'

import { MessageSquare } from 'lucide-react'
import { useCallback, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { AgentMessageList } from './AgentMessageList'
import { AgentPanelHeader } from './AgentPanelHeader'
import { ChatInput } from './ChatInput'
import { ConnectionErrorBanner } from './ConnectionErrorBanner'
import { EvidenceCaptureModal } from './EvidenceCaptureModal'
import {
  useAgentPanelActions,
  useAgentPanelState,
  useAgentPanelUI,
  useSessionManagement,
  useWebSocketConnection,
} from './hooks'
import { PermissionRequestPanel } from './PermissionRequestPanel'
import { SessionsPanel } from './SessionsPanel'
import { SettingsModal } from './SettingsModal'
import { StatusModal } from './StatusModal'
import { TokenSummaryCards } from './TokenSummaryCards'

// Layout class constants
const PANEL_FIXED =
  'fixed top-16 right-0 z-40 h-[calc(100vh-4rem)] w-[500px] flex flex-col bg-bg text-text border-l border-border shadow-2xl transition-transform duration-300 ease-in-out'
const PANEL_STANDALONE = 'h-full w-full flex flex-col bg-bg text-text'

interface AgentPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  pageContext?: { path: string; data?: Record<string, unknown> }
  /** When true, renders as full-page content without fixed positioning (for popup window) */
  standalone?: boolean
}

export function AgentPanel({
  open,
  onOpenChange: _onOpenChange,
  pageContext,
  standalone = false,
}: AgentPanelProps) {
  // Note: _onOpenChange is received from callers but not used internally yet
  void _onOpenChange

  const {
    serverUrl, wsUrl,
    isConnected, setIsConnected,
    connectionError, setConnectionError,
    messages, setMessages,
    input, setInput,
    isLoading, setIsLoading,
    currentResponse, setCurrentResponse,
    pendingPermission, setPendingPermission,
    agentProvider, setAgentProvider,
    agentMode, setAgentMode,
    roundtableOrder, setRoundtableOrder,
    maxTurns, setMaxTurns,
    currentRespondingAgent, setCurrentRespondingAgent,
    messagesEndRef, currentResponseRef,
  } = useAgentPanelState()

  const {
    showSessions, showSettings, showStatus, showTokenSummary, showEvidenceCapture,
    setShowSessions, setShowSettings, setShowStatus, setShowTokenSummary, setShowEvidenceCapture,
    toggleSessions,
  } = useAgentPanelUI()

  const {
    sessions, currentSessionId, setCurrentSessionId, currentSession,
    isLoadingSessions, createSession: createSessionBase, deleteSession, saveEvidenceToServer,
  } = useSessionManagement({ serverUrl, open, setMessages, setCurrentResponse, setIsLoading })

  const createSession = useCallback(async () => {
    await createSessionBase()
    setShowSessions(false)
  }, [createSessionBase, setShowSessions])

  const { wsRef, connect } = useWebSocketConnection({
    wsUrl, currentSessionId, open, agentProvider, roundtableOrder, maxTurns,
    currentRespondingAgent, currentResponseRef, setCurrentResponse, setCurrentRespondingAgent,
    setMessages, setIsLoading, setPendingPermission, setIsConnected, setConnectionError,
  })

  useEffect(() => { currentResponseRef.current = currentResponse }, [currentResponse, currentResponseRef])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messagesEndRef])

  const { sendMessage, stopResponse, handlePermissionResponse, handleKeyPress, handleEvidenceCaptured } =
    useAgentPanelActions({
      input, setInput, messages, setMessages, isLoading, isConnected,
      agentMode, agentProvider, pendingPermission, setPendingPermission,
      setIsLoading, wsRef, pageContext, currentSessionId, saveEvidenceToServer,
    })

  if (!open && !standalone)
    return (
      <>
        <SettingsModal open={showSettings} onOpenChange={setShowSettings} />
        <StatusModal open={showStatus} onOpenChange={setShowStatus} />
      </>
    )

  const wrapperClasses = standalone
    ? PANEL_STANDALONE
    : cn(PANEL_FIXED, open ? 'translate-x-0' : 'translate-x-full')

  return (
    <>
      <div className={wrapperClasses}>
        <AgentPanelHeader
          isConnected={isConnected}
          pageContext={pageContext}
          currentSessionId={currentSessionId}
          currentSession={currentSession}
          agentProvider={agentProvider}
          showSessions={showSessions}
          onShowEvidenceCapture={() => setShowEvidenceCapture(true)}
          onShowStatus={() => setShowStatus(true)}
          onShowSettings={() => setShowSettings(true)}
          onToggleSessions={toggleSessions}
        />
        {showTokenSummary && <TokenSummaryCards serverUrl={serverUrl || ''} />}
        {showSessions && (
          <SessionsPanel
            sessions={sessions}
            currentSessionId={currentSessionId}
            isLoadingSessions={isLoadingSessions}
            showTokenSummary={showTokenSummary}
            onSessionSelect={(sessionId) => { setCurrentSessionId(sessionId); setShowSessions(false) }}
            onCreateSession={createSession}
            onDeleteSession={deleteSession}
            onToggleTokenSummary={() => setShowTokenSummary(!showTokenSummary)}
          />
        )}
        {connectionError && !isConnected && (
          <ConnectionErrorBanner
            error={connectionError}
            onRetry={() => { setConnectionError(null); connect() }}
          />
        )}
        <AgentMessageList
          messages={messages}
          currentResponse={currentResponse}
          currentRespondingAgent={currentRespondingAgent}
          messagesEndRef={messagesEndRef}
        />
        {pendingPermission && (
          <PermissionRequestPanel permission={pendingPermission} onRespond={handlePermissionResponse} />
        )}
        <ChatInput
          input={input} onInputChange={setInput}
          onSend={sendMessage} onStop={stopResponse} onKeyPress={handleKeyPress}
          isConnected={isConnected} isLoading={isLoading}
          hasPendingPermission={!!pendingPermission} hasSession={!!currentSessionId}
          agentMode={agentMode} agentProvider={agentProvider}
          roundtableOrder={roundtableOrder} maxTurns={maxTurns}
          onAgentProviderChange={setAgentProvider} onAgentModeChange={setAgentMode}
          onRoundtableOrderChange={setRoundtableOrder} onMaxTurnsChange={setMaxTurns}
        />
      </div>
      <SettingsModal open={showSettings} onOpenChange={setShowSettings} />
      <StatusModal open={showStatus} onOpenChange={setShowStatus} />
      <EvidenceCaptureModal
        open={showEvidenceCapture}
        onClose={() => setShowEvidenceCapture(false)}
        pageUrl={pageContext?.path
          ? `${typeof window !== 'undefined' ? window.location.origin : ''}${pageContext.path}`
          : ''}
        onCaptured={handleEvidenceCaptured}
      />
    </>
  )
}

// Trigger button for the panel
export function AgentPanelTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-6 right-6 z-40 w-14 h-14 bg-primary hover:bg-primary/80 text-primary-foreground rounded-full shadow-lg flex items-center justify-center transition-transform hover:scale-105"
      title="Open Agent Hub"
    >
      <MessageSquare className="h-6 w-6" />
    </button>
  )
}
