'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { MessageSquare, Settings, Activity, Camera, Diamond, Star } from 'lucide-react';
// Note: We use a custom side panel instead of Sheet to allow non-overlay behavior (FEAT-220)
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { SettingsModal } from './SettingsModal';
import { StatusModal } from './StatusModal';
import { AgentProvider, RoundtableOrder } from './AgentSelector';
import { AgentMode } from './ModeSelector';
import { TokenSummaryCards } from './TokenSummaryCards';
import { EvidenceCaptureModal } from './EvidenceCaptureModal';
import { ProviderBadge } from './ProviderBadge';
import { SessionsPanel } from './SessionsPanel';
import { ChatInput } from './ChatInput';
import { MessageBubble, ContentBlockView } from './MessageBubble';
import { EvidenceMessageBubble } from './EvidenceMessageBubble';
import { PermissionRequestPanel } from './PermissionRequestPanel';
import {
  type ContentBlock,
  type PermissionRequest,
  type EvidenceData,
  type ChatMessage,
} from './wsHandlers';
import { useWebSocketConnection, useSessionManagement, useAgentPanelUI } from './hooks';
import { getServerUrl, getWsUrl } from '@/lib/server-url';
import { SUMMITFLOW_API } from './constants';

// AgentRole is now handled by ModeSelector

interface AgentPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pageContext?: {
    path: string;
    data?: Record<string, unknown>;
  };
  /** When true, renders as full-page content without fixed positioning (for popup window) */
  standalone?: boolean;
}

export function AgentPanel({ open, onOpenChange: _onOpenChange, pageContext, standalone = false }: AgentPanelProps) {
  // Note: _onOpenChange is received from callers but not used internally yet
  void _onOpenChange;

  // Server/connection state
  const [serverUrl] = useState<string | null>(() => getServerUrl());
  const [wsUrl] = useState<string | null>(() => {
    const url = getServerUrl();
    return url ? getWsUrl(url) : null;
  });
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentResponse, setCurrentResponse] = useState<ContentBlock[]>([]);
  const [pendingPermission, setPendingPermission] = useState<PermissionRequest | null>(null);

  // FEAT-223: Agent and mode selectors
  const [agentProvider, setAgentProvider] = useState<AgentProvider>('claude');
  const [agentMode, setAgentMode] = useState<AgentMode>('dev');
  const [roundtableOrder, setRoundtableOrder] = useState<RoundtableOrder>('claude-first');
  const [maxTurns, setMaxTurns] = useState<number>(10);
  const [currentRespondingAgent, setCurrentRespondingAgent] = useState<'claude' | 'gemini' | null>(null);

  // UI state - extracted to hook for reusability
  const {
    showSessions,
    showSettings,
    showStatus,
    showTokenSummary,
    showEvidenceCapture,
    setShowSessions,
    setShowSettings,
    setShowStatus,
    setShowTokenSummary,
    setShowEvidenceCapture,
    toggleSessions,
  } = useAgentPanelUI();

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentResponseRef = useRef<ContentBlock[]>([]);

  // Keep ref in sync with state
  useEffect(() => {
    currentResponseRef.current = currentResponse;
  }, [currentResponse]);

  // Session management hook
  const {
    sessions,
    currentSessionId,
    setCurrentSessionId,
    currentSession,
    isLoadingSessions,
    createSession: createSessionBase,
    deleteSession,
    saveEvidenceToServer,
  } = useSessionManagement({
    serverUrl,
    open,
    setMessages,
    setCurrentResponse,
    setIsLoading,
  });

  // Wrap createSession to also close the sessions panel
  const createSession = useCallback(async () => {
    await createSessionBase();
    setShowSessions(false);
  }, [createSessionBase, setShowSessions]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentResponse]);

  // WebSocket connection hook
  const { wsRef, connect } = useWebSocketConnection({
    wsUrl,
    currentSessionId,
    open,
    agentProvider,
    roundtableOrder,
    maxTurns,
    currentRespondingAgent,
    currentResponseRef,
    setCurrentResponse,
    setCurrentRespondingAgent,
    setMessages,
    setIsLoading,
    setPendingPermission,
    setIsConnected,
    setConnectionError,
  });

  // Build evidence context from recent captures (last 5)
  const buildEvidenceContext = useCallback(() => {
    const evidenceMessages = messages
      .filter((msg): msg is ChatMessage & { evidence: EvidenceData } =>
        msg.role === 'evidence' && !!msg.evidence
      )
      .slice(-5); // Last 5 evidence captures

    if (evidenceMessages.length === 0) return '';

    const evidenceLines = evidenceMessages.map((msg) => {
      const e = msg.evidence;
      const screenshotUrl = `${SUMMITFLOW_API}/evidence/${e.featureId}/${e.criterionId}/screenshot`;
      return `[Evidence: ${e.featureId}/${e.criterionId} v${e.version} - ${e.consoleErrors} console errors, ${e.networkFailures} network failures - screenshot: ${screenshotUrl}]`;
    });

    return `\n--- Available Evidence ---\n${evidenceLines.join('\n')}\n---\n\n`;
  }, [messages]);

  // Send message
  const sendMessage = () => {
    console.log('sendMessage called:', {
      hasInput: !!input.trim(),
      hasWs: !!wsRef.current,
      wsState: wsRef.current?.readyState,
      isLoading,
      isConnected,
      agentProvider
    });
    if (!input.trim() || !wsRef.current || isLoading) return;

    const message = input.trim();

    // Inject page context if in financial mode
    let contextPrefix = '';
    if (agentMode === 'financial' && pageContext) {
      contextPrefix = `[Page: ${pageContext.path}]\n`;
      if (pageContext.data) {
        contextPrefix += `[Context: ${JSON.stringify(pageContext.data)}]\n\n`;
      }
    }

    // Inject evidence context if any captures exist in the conversation
    const evidenceContext = buildEvidenceContext();

    setInput('');
    setIsLoading(true);

    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        content: message,
        timestamp: new Date(),
      },
    ]);

    wsRef.current.send(JSON.stringify({
      type: 'message',
      content: contextPrefix + evidenceContext + message,
    }));
  };

  // Stop response
  const stopResponse = () => {
    if (!wsRef.current || !isLoading) return;
    wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
    setIsLoading(false);
    setPendingPermission(null);
  };

  // Handle permission
  const handlePermissionResponse = (allowed: boolean) => {
    if (!wsRef.current || !pendingPermission) return;

    wsRef.current.send(JSON.stringify({
      type: 'permission_response',
      allowed,
    }));

    setMessages(prev => [
      ...prev,
      {
        role: 'system',
        content: `Permission ${allowed ? 'ALLOWED' : 'DENIED'} for: ${pendingPermission.toolName}`,
        timestamp: new Date(),
      },
    ]);

    setPendingPermission(null);
  };

  // Key press handler
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Don't render anything if closed (unless standalone mode - always render)
  if (!open && !standalone) return (
    <>
      <SettingsModal open={showSettings} onOpenChange={setShowSettings} />
      <StatusModal open={showStatus} onOpenChange={setShowStatus} />
    </>
  );

  // Standalone mode: full-page content for popup window
  // Panel mode: fixed side panel attached to right
  const wrapperClasses = standalone
    ? "h-full w-full flex flex-col bg-bg text-text"
    : cn(
        "fixed top-16 right-0 z-40 h-[calc(100vh-4rem)] w-[500px] flex flex-col bg-bg text-text border-l border-border shadow-2xl",
        "transition-transform duration-300 ease-in-out",
        open ? "translate-x-0" : "translate-x-full"
      );

  return (
    <>
      {/* Side Panel or Standalone Content (FEAT-220) */}
      <div className={wrapperClasses}>
        {/* Header - FEAT-223: 5 icons layout */}
        <div className="p-4 border-b border-border space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-text">Agent Hub</h2>
              <span className={cn(
                "w-2 h-2 rounded-full",
                isConnected ? "bg-gain" : "bg-loss"
              )} />
            </div>
            {/* Header Icons: Evidence, Status, Settings */}
            <div className="flex items-center gap-1">
              {/* Evidence Capture */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowEvidenceCapture(true)}
                disabled={!pageContext?.path}
                className="h-8 w-8 p-0 text-text-muted hover:text-text disabled:opacity-50"
                title={pageContext?.path ? "Capture page evidence" : "No page context"}
              >
                <Camera className="h-4 w-4" />
              </Button>
              {/* Status */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowStatus(true)}
                className="h-8 w-8 p-0 text-text-muted hover:text-text"
                title="Status"
              >
                <Activity className="h-4 w-4" />
              </Button>
              {/* Settings */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSettings(true)}
                className="h-8 w-8 p-0 text-text-muted hover:text-text"
                title="Settings"
              >
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>
          {/* Page context indicator */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-text-muted">Tracking:</span>
            <span className={cn(
              "font-mono px-1.5 py-0.5 rounded",
              pageContext?.path
                ? "bg-primary-surface text-primary"
                : "bg-surface-muted text-text-muted"
            )}>
              {pageContext?.path || "No page"}
            </span>
          </div>
          {/* Sessions button (left) + Session ID + Provider info (right) */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {/* Sessions Button - left side */}
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleSessions}
                className={cn(
                  "h-7 px-2 text-text-muted hover:text-text text-xs",
                  showSessions && "bg-surface-muted text-text"
                )}
                title="Sessions"
              >
                <MessageSquare className="h-3.5 w-3.5 mr-1" />
                Sessions
              </Button>
              <span className="text-border">|</span>
              <span className="text-text-muted text-xs flex items-center gap-1">
                {currentSessionId ? `${currentSessionId.slice(0, 8)}...` : 'No session'}
                {/* Show original provider badge if session has one */}
                {currentSession?.originalProvider && (
                  <ProviderBadge provider={currentSession.originalProvider} size="xs" />
                )}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {/* Show "Started with: X" if current agent differs from original */}
              {currentSession?.originalProvider &&
               currentSession.originalProvider !== 'both' &&
               currentSession.originalProvider !== agentProvider && (
                <span className="text-xs text-text-muted flex items-center gap-1">
                  Started with: <ProviderBadge provider={currentSession.originalProvider} size="xs" />
                </span>
              )}
              {isConnected && (
                <span className={cn(
                  "text-xs px-1.5 py-0.5 rounded font-medium",
                  agentProvider === 'both'
                    ? "bg-accent/30 text-accent border border-accent"
                    : agentProvider === 'gemini'
                      ? "bg-gain/30 text-gain border border-gain"
                      : "bg-primary/30 text-primary border border-primary"
                )}>
                  {agentProvider === 'both'
                    ? 'Claude + Gemini'
                    : agentProvider === 'gemini' ? 'Gemini' : 'Claude'}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Token Summary Cards - Toggleable */}
        {showTokenSummary && (
          <TokenSummaryCards serverUrl={serverUrl || ''} />
        )}


        {/* Sessions Panel (unified: create/delete + history) */}
        {showSessions && (
          <SessionsPanel
            sessions={sessions}
            currentSessionId={currentSessionId}
            isLoadingSessions={isLoadingSessions}
            showTokenSummary={showTokenSummary}
            onSessionSelect={(sessionId) => {
              setCurrentSessionId(sessionId);
              setShowSessions(false);
            }}
            onCreateSession={createSession}
            onDeleteSession={deleteSession}
            onToggleTokenSummary={() => setShowTokenSummary(!showTokenSummary)}
          />
        )}

        {/* Connection Error */}
        {connectionError && !isConnected && (
          <div className="p-3 bg-loss/30 border-b border-loss text-loss text-sm">
            {connectionError}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setConnectionError(null);
                connect();
              }}
              className="ml-2 h-6 text-xs"
            >
              Retry
            </Button>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-sm">
          {messages.map((msg, i) => (
            msg.role === 'evidence' && msg.evidence ? (
              <EvidenceMessageBubble
                key={i}
                message={msg}
                onViewEvidence={() => {
                  // Open SummitFlow evidence viewer
                  const baseUrl = process.env.NEXT_PUBLIC_SUMMITFLOW_URL || 'https://dev.summitflow.dev';
                  window.open(`${baseUrl}/projects/portfolio-ai?tab=evidence`, '_blank');
                }}
              />
            ) : (
              <MessageBubble key={i} message={msg} />
            )
          ))}

          {currentResponse.length > 0 && (
            <div className="text-text">
              {/* Show which agent is currently responding in roundtable mode */}
              {currentRespondingAgent && (
                <span
                  className="inline-block mb-1 mr-1"
                  title={currentRespondingAgent === 'claude' ? 'Claude' : 'Gemini'}
                >
                  {currentRespondingAgent === 'claude'
                    ? <Diamond className="h-4 w-4 text-primary inline" />
                    : <Star className="h-4 w-4 text-gain inline" />}
                </span>
              )}
              {currentResponse.map((block, i) => (
                <ContentBlockView key={i} block={block} />
              ))}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Permission Request */}
        {pendingPermission && (
          <PermissionRequestPanel
            permission={pendingPermission}
            onRespond={handlePermissionResponse}
          />
        )}

        {/* Input */}
        <ChatInput
          input={input}
          onInputChange={setInput}
          onSend={sendMessage}
          onStop={stopResponse}
          onKeyPress={handleKeyPress}
          isConnected={isConnected}
          isLoading={isLoading}
          hasPendingPermission={!!pendingPermission}
          hasSession={!!currentSessionId}
          agentMode={agentMode}
          agentProvider={agentProvider}
          roundtableOrder={roundtableOrder}
          maxTurns={maxTurns}
          onAgentProviderChange={setAgentProvider}
          onAgentModeChange={setAgentMode}
          onRoundtableOrderChange={setRoundtableOrder}
          onMaxTurnsChange={setMaxTurns}
        />
      </div>

      {/* Settings Modal */}
      <SettingsModal open={showSettings} onOpenChange={setShowSettings} />

      {/* Status Modal */}
      <StatusModal open={showStatus} onOpenChange={setShowStatus} />

      {/* Evidence Capture Modal */}
      <EvidenceCaptureModal
        open={showEvidenceCapture}
        onClose={() => setShowEvidenceCapture(false)}
        pageUrl={pageContext?.path ? `${typeof window !== 'undefined' ? window.location.origin : ''}${pageContext.path}` : ''}
        onCaptured={(result) => {
          // Create evidence message
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
          };

          // Add to chat and persist to server
          setMessages((prev) => [...prev, evidenceMsg]);
          if (currentSessionId) {
            saveEvidenceToServer(currentSessionId, evidenceMsg);
          }
        }}
      />
    </>
  );
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
  );
}
