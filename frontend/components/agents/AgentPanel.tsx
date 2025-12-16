'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { MessageSquare, X, Plus, Trash2, Settings, Activity, Diamond, Star, Camera, Eye } from 'lucide-react';
// Note: We use a custom side panel instead of Sheet to allow non-overlay behavior (FEAT-220)
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { SettingsModal, useAgentSettings, LLMProvider } from './SettingsModal';
import { StatusModal } from './StatusModal';
import { AgentSelector, AgentProvider, RoundtableOrder } from './AgentSelector';
import { ModeSelector, AgentMode } from './ModeSelector';
import { TokenSummaryCards } from './TokenSummaryCards';
import { DevCompanionSessionsList } from './SessionsList';
import { EvidenceCaptureModal } from './EvidenceCaptureModal';
import { EvidenceViewerModal } from '../capabilities/EvidenceViewerModal';

// Types from ChatPanel
interface ContentBlock {
  type: 'text' | 'tool_use' | 'tool_result' | 'thinking';
  text?: string | null;
  tool_name?: string | null;
  tool_input?: Record<string, unknown> | null;
  tool_use_id?: string | null;
  is_error?: boolean;
}

interface StreamMessage {
  type: 'assistant' | 'user' | 'system' | 'result';
  content: ContentBlock[];
  model?: string | null;
  stop_reason?: string | null;
  session_id?: string | null;
}

interface PermissionRequest {
  tool_name: string;
  tool_input: Record<string, unknown>;
}

interface WebSocketMessage {
  type: 'stream' | 'done' | 'error' | 'pong' | 'permission_request' | 'interrupt_ack' | 'provider' | 'agent_start' | 'agent_done' | 'discussion_start' | 'discussion_round';
  data?: StreamMessage;
  message?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  success?: boolean;
  name?: string;  // For provider confirmation
  agent?: 'claude' | 'gemini';  // Which agent is responding (roundtable mode)
  round?: number;  // Discussion round number
  reason?: string;  // Reason for discussion (e.g., 'disagreement_detected')
}

interface EvidenceData {
  feature_id: string;
  criterion_id: string;
  version: number;
  console_errors: number;
  network_failures: number;
  url: string;
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'evidence';
  content: string;
  blocks?: ContentBlock[];
  timestamp: Date;
  agent?: 'claude' | 'gemini';  // Which agent produced this response (roundtable mode)
  evidence?: EvidenceData;  // Evidence capture data
}

interface Session {
  id: string;
  working_dir: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  metadata: Record<string, unknown>;
  original_provider?: string | null;
  message_count?: number;
  description?: string | null;
  participants?: string[];
}

// Provider badge component for session attribution
function ProviderBadge({ provider, size = 'sm' }: { provider: string | null | undefined; size?: 'sm' | 'xs' }) {
  if (!provider) return null;

  const iconClass = size === 'xs' ? 'h-3 w-3' : 'h-4 w-4';

  if (provider === 'claude') {
    return <span title="Claude"><Diamond className={`${iconClass} text-blue-400`} /></span>;
  }
  if (provider === 'gemini') {
    return <span title="Gemini"><Star className={`${iconClass} text-green-400`} /></span>;
  }
  if (provider === 'both') {
    return (
      <span className="flex -space-x-1" title="Claude + Gemini">
        <Diamond className={`${iconClass} text-blue-400`} />
        <Star className={`${iconClass} text-green-400`} />
      </span>
    );
  }
  return null;
}

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

// Get server URL based on current hostname
// Use nginx proxy path /dev-companion/ for SSL termination
const getServerUrl = () => {
  if (typeof window === 'undefined') return null;
  if (process.env.NEXT_PUBLIC_DEV_COMPANION_URL) {
    return process.env.NEXT_PUBLIC_DEV_COMPANION_URL;
  }
  // Use proxied path through nginx (handles SSL)
  return `${window.location.origin}/dev-companion`;
};

export function AgentPanel({ open, onOpenChange, pageContext, standalone = false }: AgentPanelProps) {
  // Settings (includes llmProvider)
  const settings = useAgentSettings();

  // Server/connection state
  const [serverUrl, setServerUrl] = useState<string | null>(null);
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [activeProvider, setActiveProvider] = useState<LLMProvider>('claude');

  // Session state
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);

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

  // UI state
  const [showSessions, setShowSessions] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showStatus, setShowStatus] = useState(false);
  const [showTokenSummary, setShowTokenSummary] = useState(false);
  const [showEvidenceCapture, setShowEvidenceCapture] = useState(false);
  const [evidenceViewer, setEvidenceViewer] = useState<{
    open: boolean;
    featureId: string;
    criterionId: string;
  }>({ open: false, featureId: '', criterionId: '' });

  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentResponseRef = useRef<ContentBlock[]>([]);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const intentionalCloseRef = useRef(false); // Prevent reconnect on provider switch

  // Initialize URLs on client
  useEffect(() => {
    const url = getServerUrl();
    if (url) {
      setServerUrl(url);
      setWsUrl(url.replace(/^http/, 'ws'));
    }
  }, []);

  // Keep ref in sync with state
  useEffect(() => {
    currentResponseRef.current = currentResponse;
  }, [currentResponse]);

  // Fetch sessions
  const fetchSessions = useCallback(async () => {
    if (!serverUrl) return;
    try {
      const response = await fetch(`${serverUrl}/sessions`);
      if (!response.ok) throw new Error('Failed to fetch sessions');
      const data = await response.json();
      setSessions(data);
      if (data.length > 0 && !currentSessionId) {
        setCurrentSessionId(data[0].id);
      }
    } catch {
      setConnectionError('Failed to connect to Dev Companion server');
    } finally {
      setIsLoadingSessions(false);
    }
  }, [serverUrl, currentSessionId]);

  useEffect(() => {
    if (serverUrl && open) {
      fetchSessions();
    }
  }, [serverUrl, open, fetchSessions]);

  // Save evidence message to server
  const saveEvidenceToServer = useCallback(async (sessionId: string, evidenceMsg: ChatMessage) => {
    if (!sessionId || !serverUrl) return;
    try {
      await fetch(`${serverUrl}/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: 'evidence',
          content: evidenceMsg.content,
          metadata: { evidence: evidenceMsg.evidence },
        }),
      });
    } catch (err) {
      console.error('Failed to save evidence to server:', err);
    }
  }, [serverUrl]);

  // Load history when session changes
  useEffect(() => {
    if (!serverUrl || !currentSessionId) return;

    const loadHistory = async () => {
      try {
        const res = await fetch(`${serverUrl}/sessions/${currentSessionId}/history`);
        if (res.ok) {
          const data = await res.json();
          const loadedMessages: ChatMessage[] = data.messages.map((msg: { role: string; content: string; created_at: string; agent?: string; metadata?: { evidence?: EvidenceData } }) => ({
            role: msg.role as 'user' | 'assistant' | 'system' | 'evidence',
            content: msg.content,
            timestamp: new Date(msg.created_at),
            agent: msg.agent as 'claude' | 'gemini' | undefined,
            evidence: msg.metadata?.evidence,
          }));

          setMessages(loadedMessages);
        }
      } catch (err) {
        console.error('Failed to load history:', err);
      }
    };

    setMessages([]);
    setCurrentResponse([]);
    setIsLoading(false);
    loadHistory();
  }, [currentSessionId, serverUrl]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentResponse]);

  // Track connection generation to prevent stale reconnects
  const connectionGenRef = useRef(0);

  // Connect WebSocket
  const connect = useCallback(() => {
    if (!wsUrl || !currentSessionId || !open) return;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    // Increment generation to invalidate stale onclose handlers
    const thisGeneration = ++connectionGenRef.current;

    // Use agentProvider from selector (claude/gemini/both), with order and maxTurns for roundtable
    const providerParam = agentProvider === 'both' ? 'both' : agentProvider;
    const orderParam = agentProvider === 'both' ? `&order=${roundtableOrder}&max_turns=${maxTurns}` : '';
    const ws = new WebSocket(`${wsUrl}/ws/${currentSessionId}?provider=${providerParam}${orderParam}`);

    ws.onopen = () => {
      // Only update state if this is still the current connection generation
      // This prevents race conditions when rapidly switching providers
      if (thisGeneration === connectionGenRef.current) {
        setIsConnected(true);
        setConnectionError(null);
        console.log('WebSocket opened, generation:', thisGeneration);
      }
    };

    ws.onclose = () => {
      // Only update state if this is still the current connection generation
      // This prevents stale onclose from old connections affecting the new connection
      if (thisGeneration === connectionGenRef.current) {
        setIsConnected(false);
        wsRef.current = null;
        console.log('WebSocket closed, generation:', thisGeneration);
        // Only reconnect if this wasn't an intentional close
        if (open && !intentionalCloseRef.current) {
          reconnectTimeoutRef.current = setTimeout(connect, 3000);
        }
      } else {
        console.log('Ignoring stale onclose for generation:', thisGeneration, 'current:', connectionGenRef.current);
      }
    };

    ws.onerror = () => {
      setConnectionError(`Failed to connect to ${ws.url}`);
    };

    ws.onmessage = (event) => {
      const msg: WebSocketMessage = JSON.parse(event.data);

      switch (msg.type) {
        case 'stream':
          if (msg.data) {
            setCurrentResponse(prev => [...prev, ...msg.data!.content]);
          }
          break;

        case 'agent_start':
          // Roundtable: Track which agent is now responding
          if (msg.agent) {
            setCurrentRespondingAgent(msg.agent);
          }
          break;

        case 'agent_done': {
          // Roundtable: Save current agent's response with attribution
          const blocks = currentResponseRef.current;
          if (blocks.length > 0) {
            setMessages(prev => [
              ...prev,
              {
                role: 'assistant',
                content: blocksToText(blocks),
                blocks: blocks,
                timestamp: new Date(),
                agent: msg.agent,  // Attribution for roundtable mode
              },
            ]);
          }
          setCurrentResponse([]);
          setCurrentRespondingAgent(null);
          break;
        }

        case 'discussion_start':
          // Roundtable: Show system message that discussion is starting
          setMessages(prev => [
            ...prev,
            {
              role: 'system',
              content: `Agents disagree — starting discussion...`,
              timestamp: new Date(),
            },
          ]);
          break;

        case 'discussion_round':
          // Roundtable: Show which round we're in
          if (msg.round) {
            setMessages(prev => [
              ...prev,
              {
                role: 'system',
                content: `Discussion round ${msg.round}`,
                timestamp: new Date(),
              },
            ]);
          }
          break;

        case 'done': {
          const blocks = currentResponseRef.current;
          if (blocks.length > 0) {
            // Determine agent: roundtable uses currentRespondingAgent, single-mode uses agentProvider
            const agent = currentRespondingAgent
              || (agentProvider !== 'both' ? agentProvider : undefined);
            setMessages(prev => [
              ...prev,
              {
                role: 'assistant',
                content: blocksToText(blocks),
                blocks: blocks,
                timestamp: new Date(),
                agent,
              },
            ]);
          }
          setCurrentResponse([]);
          setCurrentRespondingAgent(null);
          setIsLoading(false);
          break;
        }

        case 'error':
          setMessages(prev => [
            ...prev,
            {
              role: 'system',
              content: `Error: ${msg.message}`,
              timestamp: new Date(),
            },
          ]);
          setIsLoading(false);
          setPendingPermission(null);
          setCurrentRespondingAgent(null);
          break;

        case 'permission_request':
          if (msg.tool_name && msg.tool_input) {
            setPendingPermission({
              tool_name: msg.tool_name,
              tool_input: msg.tool_input,
            });
          }
          break;

        case 'interrupt_ack':
          setPendingPermission(null);
          break;

        case 'provider':
          // Server confirms which provider is active
          if (msg.name) {
            setActiveProvider(msg.name as LLMProvider);
          }
          break;
      }
    };

    wsRef.current = ws;
  }, [wsUrl, currentSessionId, open, agentProvider, roundtableOrder, maxTurns]);

  // Connect/disconnect based on panel state
  useEffect(() => {
    // Reset intentional close flag before connecting
    intentionalCloseRef.current = false;

    if (open && currentSessionId) {
      connect();
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        // Mark as intentional close to prevent reconnect with stale provider
        intentionalCloseRef.current = true;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [open, currentSessionId, connect]);

  // Create session
  const createSession = async () => {
    if (!serverUrl) return;
    try {
      const response = await fetch(`${serverUrl}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          working_dir: '/home/kasadis/portfolio-ai',
        }),
      });
      if (!response.ok) throw new Error('Failed to create session');
      const session = await response.json();
      setSessions(prev => [session, ...prev]);
      setCurrentSessionId(session.id);
      setShowSessions(false);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  // Delete session
  const deleteSession = async (sessionId: string) => {
    if (!serverUrl) return;
    try {
      const response = await fetch(`${serverUrl}/sessions/${sessionId}`, { method: 'DELETE' });
      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }
      // Clear chat if deleting current session BEFORE updating session ID
      if (currentSessionId === sessionId) {
        setMessages([]);
        setCurrentResponse([]);
      }
      // Only update local state after confirmed deletion
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        setCurrentSessionId(sessions.find(s => s.id !== sessionId)?.id || null);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
      toast.error('Failed to delete session');
    }
  };

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
      const screenshotUrl = `/api/artifacts/${e.feature_id}/${e.criterion_id}/screenshot`;
      return `[Evidence: ${e.feature_id}/${e.criterion_id} v${e.version} - ${e.console_errors} console errors, ${e.network_failures} network failures - screenshot: ${screenshotUrl}]`;
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
        content: `Permission ${allowed ? 'ALLOWED' : 'DENIED'} for: ${pendingPermission.tool_name}`,
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
    ? "h-full w-full flex flex-col bg-gray-900 text-gray-100"
    : cn(
        "fixed top-16 right-0 z-40 h-[calc(100vh-4rem)] w-[500px] flex flex-col bg-gray-900 text-gray-100 border-l border-gray-700 shadow-2xl",
        "transition-transform duration-300 ease-in-out",
        open ? "translate-x-0" : "translate-x-full"
      );

  return (
    <>
      {/* Side Panel or Standalone Content (FEAT-220) */}
      <div className={wrapperClasses}>
        {/* Header - FEAT-223: 5 icons layout */}
        <div className="p-4 border-b border-gray-700 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-gray-100">Agent Hub</h2>
              <span className={cn(
                "w-2 h-2 rounded-full",
                isConnected ? "bg-green-500" : "bg-red-500"
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
                className="h-8 w-8 p-0 text-gray-400 hover:text-gray-100 disabled:opacity-50"
                title={pageContext?.path ? "Capture page evidence" : "No page context"}
              >
                <Camera className="h-4 w-4" />
              </Button>
              {/* Status */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowStatus(true)}
                className="h-8 w-8 p-0 text-gray-400 hover:text-gray-100"
                title="Status"
              >
                <Activity className="h-4 w-4" />
              </Button>
              {/* Settings */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSettings(true)}
                className="h-8 w-8 p-0 text-gray-400 hover:text-gray-100"
                title="Settings"
              >
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>
          {/* Page context indicator */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-500">Tracking:</span>
            <span className={cn(
              "font-mono px-1.5 py-0.5 rounded",
              pageContext?.path
                ? "bg-blue-500/20 text-blue-300"
                : "bg-gray-700 text-gray-500"
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
                onClick={() => {
                  setShowSessions(!showSessions);
                  setShowTokenSummary(false);
                }}
                className={cn(
                  "h-7 px-2 text-gray-400 hover:text-gray-100 text-xs",
                  showSessions && "bg-gray-700 text-gray-100"
                )}
                title="Sessions"
              >
                <MessageSquare className="h-3.5 w-3.5 mr-1" />
                Sessions
              </Button>
              <span className="text-gray-600">|</span>
              <span className="text-gray-500 text-xs flex items-center gap-1">
                {currentSessionId ? `${currentSessionId.slice(0, 8)}...` : 'No session'}
                {/* Show original provider badge if session has one */}
                {(() => {
                  const currentSession = sessions.find(s => s.id === currentSessionId);
                  return currentSession?.original_provider && (
                    <ProviderBadge provider={currentSession.original_provider} size="xs" />
                  );
                })()}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {/* Show "Started with: X" if current agent differs from original */}
              {(() => {
                const currentSession = sessions.find(s => s.id === currentSessionId);
                const originalProvider = currentSession?.original_provider;
                if (originalProvider && originalProvider !== 'both' && originalProvider !== agentProvider) {
                  return (
                    <span className="text-xs text-gray-500 flex items-center gap-1">
                      Started with: <ProviderBadge provider={originalProvider} size="xs" />
                    </span>
                  );
                }
                return null;
              })()}
              {isConnected && (
                <span className={cn(
                  "text-xs px-1.5 py-0.5 rounded font-medium",
                  agentProvider === 'both'
                    ? "bg-purple-600/30 text-purple-300 border border-purple-600"
                    : agentProvider === 'gemini'
                      ? "bg-green-600/30 text-green-300 border border-green-600"
                      : "bg-blue-600/30 text-blue-300 border border-blue-600"
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
          <div className="border-b border-gray-700 bg-gray-800/30">
            <div className="p-2 flex items-center justify-between border-b border-gray-700">
              <span className="text-xs text-gray-400 font-medium">Sessions</span>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowTokenSummary(!showTokenSummary)}
                  className="h-6 px-2 text-xs text-gray-400 hover:text-gray-100"
                >
                  {showTokenSummary ? 'Hide Tokens' : 'Show Tokens'}
                </Button>
                <Button size="sm" variant="ghost" onClick={createSession} className="h-6 px-2 text-xs text-green-400 hover:text-green-300">
                  <Plus className="h-3 w-3 mr-1" /> New
                </Button>
              </div>
            </div>
            {isLoadingSessions ? (
              <div className="p-4 text-center text-gray-500 text-sm">Loading...</div>
            ) : sessions.length === 0 ? (
              <div className="p-4 text-center text-gray-500 text-sm">No sessions yet</div>
            ) : (
              <div className="overflow-y-auto" style={{ maxHeight: '250px' }}>
                {sessions.map(session => (
                  <div
                    key={session.id}
                    className={cn(
                      "p-3 border-b border-gray-700 hover:bg-gray-800/50 cursor-pointer transition-colors",
                      currentSessionId === session.id && "bg-gray-700"
                    )}
                    onClick={() => {
                      setCurrentSessionId(session.id);
                      setShowSessions(false);
                    }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        {/* Session ID + Provider Badge */}
                        <div className="flex items-center gap-2 mb-1">
                          <span className={cn(
                            "w-2 h-2 rounded-full",
                            session.is_active ? "bg-green-500" : "bg-gray-600"
                          )} />
                          <span className="font-mono text-sm text-gray-300">
                            {session.id.slice(0, 8)}
                          </span>
                          <ProviderBadge provider={session.original_provider} size="xs" />
                        </div>
                        {/* Description or placeholder */}
                        <div className="text-xs text-gray-400 truncate">
                          {session.description || (session.message_count ? 'No description' : '(No messages yet)')}
                        </div>
                        {/* Participants row */}
                        {session.participants && session.participants.length > 0 && (
                          <div className="flex items-center gap-1 mt-1">
                            <span className="text-[10px] text-gray-600">Participants:</span>
                            {session.participants.map((p) => (
                              <ProviderBadge key={p} provider={p} size="xs" />
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-1 text-right">
                        {/* Message count */}
                        {session.message_count != null && session.message_count > 0 && (
                          <span className="text-xs text-gray-400">
                            {session.message_count} msgs
                          </span>
                        )}
                        {/* Relative time */}
                        <span className="text-[10px] text-gray-500">
                          {formatRelativeTime(session.updated_at)}
                        </span>
                        {/* Delete button */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteSession(session.id);
                          }}
                          className="h-6 w-6 p-0 text-gray-500 hover:text-red-400"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Connection Error */}
        {connectionError && !isConnected && (
          <div className="p-3 bg-red-900/30 border-b border-red-700 text-red-200 text-sm">
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
                  setEvidenceViewer({
                    open: true,
                    featureId: msg.evidence!.feature_id,
                    criterionId: msg.evidence!.criterion_id,
                  });
                }}
              />
            ) : (
              <MessageBubble key={i} message={msg} />
            )
          ))}

          {currentResponse.length > 0 && (
            <div className="text-gray-300">
              {/* Show which agent is currently responding in roundtable mode */}
              {currentRespondingAgent && (
                <span
                  className="inline-block mb-1 mr-1"
                  title={currentRespondingAgent === 'claude' ? 'Claude' : 'Gemini'}
                >
                  {currentRespondingAgent === 'claude'
                    ? <Diamond className="h-4 w-4 text-blue-400 inline" />
                    : <Star className="h-4 w-4 text-green-400 inline" />}
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
          <div className="border-t border-yellow-600 bg-yellow-900/30 p-4">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 text-xl">⚠</div>
              <div className="flex-1">
                <h4 className="font-semibold text-yellow-200 mb-2">Permission Required</h4>
                <p className="text-sm text-yellow-100 mb-2">
                  Claude wants to use: <span className="font-mono font-bold">{pendingPermission.tool_name}</span>
                </p>
                {pendingPermission.tool_input && Object.keys(pendingPermission.tool_input).length > 0 && (
                  <div className="bg-gray-800/50 rounded p-2 mb-3 max-h-24 overflow-y-auto">
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">
                      {JSON.stringify(pendingPermission.tool_input, null, 2)}
                    </pre>
                  </div>
                )}
                <div className="flex gap-2">
                  <Button onClick={() => handlePermissionResponse(true)} size="sm" className="bg-green-600 hover:bg-green-700">
                    Allow
                  </Button>
                  <Button onClick={() => handlePermissionResponse(false)} size="sm" variant="destructive">
                    Deny
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Input */}
        <div className="border-t border-gray-700 p-4">
          <div className="flex gap-2 items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={
                pendingPermission
                  ? "Waiting for permission..."
                  : !currentSessionId
                  ? "Create a session first..."
                  : isConnected
                  ? `Ask ${agentMode === 'dev' ? 'for code help' : 'about markets'}...`
                  : "Connecting..."
              }
              disabled={!isConnected || isLoading || !!pendingPermission || !currentSessionId}
              className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 text-sm"
            />
            {/* Agent & Mode selectors - always visible for quick toggle */}
            <AgentSelector
              value={agentProvider}
              onChange={setAgentProvider}
              disabled={!isConnected}
              roundtableOrder={roundtableOrder}
              onRoundtableOrderChange={setRoundtableOrder}
              maxTurns={maxTurns}
              onMaxTurnsChange={setMaxTurns}
            />
            <ModeSelector
              value={agentMode}
              onChange={setAgentMode}
              disabled={!isConnected}
            />
            {isLoading ? (
              <Button onClick={stopResponse} variant="destructive" size="sm">
                Stop
              </Button>
            ) : (
              <Button
                onClick={() => {
                  console.log('Send button clicked, isConnected:', isConnected, 'input:', input, 'sessionId:', currentSessionId);
                  sendMessage();
                }}
                disabled={!isConnected || !input.trim() || !!pendingPermission || !currentSessionId}
                size="sm"
              >
                Send
              </Button>
            )}
          </div>
        </div>
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
            content: `Evidence captured for ${result.feature_id}`,
            timestamp: new Date(),
            evidence: {
              feature_id: result.feature_id,
              criterion_id: result.criterion_id,
              version: result.version,
              console_errors: result.evidence?.console?.errorCount ?? 0,
              network_failures: result.evidence?.network?.failedRequests ?? 0,
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

      {/* Evidence Viewer Modal */}
      <EvidenceViewerModal
        open={evidenceViewer.open}
        onOpenChange={(open) => setEvidenceViewer((prev) => ({ ...prev, open }))}
        featureId={evidenceViewer.featureId}
        criterionId={evidenceViewer.criterionId}
      />
    </>
  );
}

// Trigger button for the panel
export function AgentPanelTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-6 right-6 z-40 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center transition-transform hover:scale-105"
      title="Open Agent Hub"
    >
      <MessageSquare className="h-6 w-6" />
    </button>
  );
}

// Helper functions
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hr ago`;
  if (diffDays === 1) return 'yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString();
}

function blocksToText(blocks: ContentBlock[]): string {
  return blocks
    .map(block => {
      if (block.type === 'text' && block.text) return block.text;
      if (block.type === 'tool_use') return `[Tool: ${block.tool_name}]`;
      if (block.type === 'tool_result') return `[Result: ${block.text}]`;
      return '';
    })
    .join('');
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3 py-2 text-sm",
          isUser
            ? 'bg-blue-600 text-white'
            : isSystem
            ? 'bg-yellow-900/50 text-yellow-200 border border-yellow-700'
            : 'bg-gray-800 text-gray-100'
        )}
      >
        {/* Agent attribution icon */}
        {message.agent && !isUser && (
          <span
            className="inline-block mb-1 mr-1"
            title={message.agent === 'claude' ? 'Claude' : 'Gemini'}
          >
            {message.agent === 'claude'
              ? <Diamond className="h-4 w-4 text-blue-400 inline" />
              : <Star className="h-4 w-4 text-green-400 inline" />}
          </span>
        )}
        {message.blocks ? (
          message.blocks.map((block, i) => <ContentBlockView key={i} block={block} />)
        ) : (
          <div className="whitespace-pre-wrap">{message.content}</div>
        )}
        <div className="text-xs opacity-50 mt-1">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

function EvidenceMessageBubble({
  message,
  onViewEvidence
}: {
  message: ChatMessage;
  onViewEvidence: () => void;
}) {
  const evidence = message.evidence!;
  const hasErrors = evidence.console_errors > 0 || evidence.network_failures > 0;

  return (
    <div className="flex justify-start">
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors",
          "bg-gray-800 hover:bg-gray-700 border",
          hasErrors ? "border-red-500/50" : "border-blue-500/50"
        )}
        onClick={onViewEvidence}
      >
        <div className="flex items-center gap-2 mb-1">
          <Camera className="h-4 w-4 text-blue-400" />
          <span className="font-medium">Evidence Captured</span>
          <span className="text-xs text-gray-500">v{evidence.version}</span>
        </div>
        <div className="text-xs text-gray-400 mb-2">
          {evidence.feature_id} / {evidence.criterion_id}
        </div>
        <div className="flex items-center gap-3 text-xs">
          {evidence.console_errors > 0 && (
            <span className="text-red-400">
              {evidence.console_errors} console error{evidence.console_errors !== 1 ? 's' : ''}
            </span>
          )}
          {evidence.network_failures > 0 && (
            <span className="text-red-400">
              {evidence.network_failures} network failure{evidence.network_failures !== 1 ? 's' : ''}
            </span>
          )}
          {!hasErrors && (
            <span className="text-green-400">No issues detected</span>
          )}
        </div>
        <div className="flex items-center gap-1 mt-2 text-xs text-blue-400">
          <Eye className="h-3 w-3" />
          Click to view evidence
        </div>
        <div className="text-xs opacity-50 mt-1">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

function ContentBlockView({ block }: { block: ContentBlock }) {
  switch (block.type) {
    case 'text':
      return <div className="whitespace-pre-wrap">{block.text}</div>;

    case 'tool_use':
      return (
        <div className="my-2 p-2 bg-gray-700/50 rounded border border-gray-600 animate-pulse">
          <div className="text-xs text-blue-400 mb-1 flex items-center gap-2">
            <span className="inline-block w-2 h-2 bg-blue-400 rounded-full animate-ping" />
            Running: {block.tool_name}
          </div>
          {block.tool_input && (
            <pre className="text-xs text-gray-400 overflow-x-auto max-h-16">
              {typeof block.tool_input === 'object'
                ? JSON.stringify(block.tool_input, null, 2).slice(0, 150)
                : String(block.tool_input).slice(0, 150)}
            </pre>
          )}
        </div>
      );

    case 'tool_result':
      return (
        <div className={cn(
          "my-2 p-2 rounded border",
          block.is_error ? 'bg-red-900/30 border-red-700' : 'bg-gray-700/30 border-gray-600'
        )}>
          <div className="text-xs text-gray-400 mb-1">Result:</div>
          <pre className="text-xs overflow-x-auto whitespace-pre-wrap">{block.text}</pre>
        </div>
      );

    case 'thinking':
      return (
        <div className="my-2 p-2 bg-purple-900/30 rounded border border-purple-700">
          <div className="text-xs text-purple-400 mb-1">Thinking...</div>
          <div className="text-xs text-gray-400 italic">{block.text}</div>
        </div>
      );

    default:
      return null;
  }
}
