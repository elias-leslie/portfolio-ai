'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { MessageSquare, X, Plus, Trash2, Settings, Activity, User, Code } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { SettingsModal, useAgentSettings, LLMProvider } from './SettingsModal';
import { StatusModal } from './StatusModal';

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
  type: 'stream' | 'done' | 'error' | 'pong' | 'permission_request' | 'interrupt_ack' | 'provider';
  data?: StreamMessage;
  message?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  success?: boolean;
  name?: string;  // For provider confirmation
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  blocks?: ContentBlock[];
  timestamp: Date;
}

interface Session {
  id: string;
  working_dir: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  metadata: Record<string, unknown>;
}

export type AgentRole = 'dev' | 'financial';

interface AgentPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pageContext?: {
    path: string;
    data?: Record<string, unknown>;
  };
}

// Get server URL based on current hostname
const getServerUrl = () => {
  if (typeof window === 'undefined') return null;
  const host = window.location.hostname;
  return process.env.NEXT_PUBLIC_DEV_COMPANION_URL || `http://${host}:9999`;
};

export function AgentPanel({ open, onOpenChange, pageContext }: AgentPanelProps) {
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

  // Role state
  const [role, setRole] = useState<AgentRole>('dev');

  // UI state
  const [showSessions, setShowSessions] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showStatus, setShowStatus] = useState(false);

  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentResponseRef = useRef<ContentBlock[]>([]);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

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

  // Load history when session changes
  useEffect(() => {
    if (!serverUrl || !currentSessionId) return;

    const loadHistory = async () => {
      try {
        const res = await fetch(`${serverUrl}/sessions/${currentSessionId}/history`);
        if (res.ok) {
          const data = await res.json();
          const loadedMessages: ChatMessage[] = data.messages.map((msg: { role: string; content: string; created_at: string }) => ({
            role: msg.role as 'user' | 'assistant' | 'system',
            content: msg.content,
            timestamp: new Date(msg.created_at),
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

    const ws = new WebSocket(`${wsUrl}/ws/${currentSessionId}?provider=${settings.llmProvider}`);

    ws.onopen = () => {
      setIsConnected(true);
      setConnectionError(null);
    };

    ws.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;
      if (open) {
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
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

        case 'done': {
          const blocks = currentResponseRef.current;
          if (blocks.length > 0) {
            setMessages(prev => [
              ...prev,
              {
                role: 'assistant',
                content: blocksToText(blocks),
                blocks: blocks,
                timestamp: new Date(),
              },
            ]);
          }
          setCurrentResponse([]);
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
  }, [wsUrl, currentSessionId, open, settings.llmProvider]);

  // Connect/disconnect based on panel state
  useEffect(() => {
    if (open && currentSessionId) {
      connect();
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
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
      await fetch(`${serverUrl}/sessions/${sessionId}`, { method: 'DELETE' });
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        setCurrentSessionId(sessions.find(s => s.id !== sessionId)?.id || null);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  // Send message
  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || isLoading) return;

    const message = input.trim();

    // Inject page context if in financial mode
    let contextPrefix = '';
    if (role === 'financial' && pageContext) {
      contextPrefix = `[Page: ${pageContext.path}]\n`;
      if (pageContext.data) {
        contextPrefix += `[Context: ${JSON.stringify(pageContext.data)}]\n\n`;
      }
    }

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
      content: contextPrefix + message,
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

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[500px] sm:max-w-[500px] p-0 flex flex-col bg-gray-900 text-gray-100 border-gray-700">
        {/* Header */}
        <SheetHeader className="p-4 border-b border-gray-700 space-y-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <SheetTitle className="text-gray-100">Agent Hub</SheetTitle>
              <span className={cn(
                "w-2 h-2 rounded-full",
                isConnected ? "bg-green-500" : "bg-red-500"
              )} />
              {isConnected && (
                <span className={cn(
                  "text-xs px-1.5 py-0.5 rounded font-medium",
                  activeProvider === 'gemini'
                    ? "bg-green-600/30 text-green-300 border border-green-600"
                    : "bg-blue-600/30 text-blue-300 border border-blue-600"
                )}>
                  {activeProvider === 'gemini' ? 'Gemini' : 'Claude'}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSessions(!showSessions)}
                className="h-8 w-8 p-0 text-gray-400 hover:text-gray-100"
                title="Sessions"
              >
                <MessageSquare className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowStatus(true)}
                className="h-8 w-8 p-0 text-gray-400 hover:text-gray-100"
                title="Status"
              >
                <Activity className="h-4 w-4" />
              </Button>
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
          <SheetDescription className="text-gray-500 text-xs">
            {currentSessionId ? `Session: ${currentSessionId}` : 'No session'}
          </SheetDescription>

          {/* Role Toggle */}
          <div className="flex gap-1 mt-2 bg-gray-800 rounded-md p-1">
            <button
              onClick={() => setRole('dev')}
              className={cn(
                "flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                role === 'dev'
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-200"
              )}
            >
              <Code className="h-3 w-3" />
              Dev
            </button>
            <button
              onClick={() => setRole('financial')}
              className={cn(
                "flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                role === 'financial'
                  ? "bg-green-600 text-white"
                  : "text-gray-400 hover:text-gray-200"
              )}
            >
              <User className="h-3 w-3" />
              Financial
            </button>
          </div>
        </SheetHeader>

        {/* Sessions Dropdown */}
        {showSessions && (
          <div className="border-b border-gray-700 bg-gray-800/50 max-h-48 overflow-y-auto">
            <div className="p-2 flex items-center justify-between border-b border-gray-700">
              <span className="text-xs text-gray-400">Sessions</span>
              <Button size="sm" variant="ghost" onClick={createSession} className="h-6 px-2 text-xs">
                <Plus className="h-3 w-3 mr-1" /> New
              </Button>
            </div>
            {isLoadingSessions ? (
              <div className="p-4 text-center text-gray-500 text-sm">Loading...</div>
            ) : sessions.length === 0 ? (
              <div className="p-4 text-center text-gray-500 text-sm">No sessions</div>
            ) : (
              sessions.map(session => (
                <div
                  key={session.id}
                  className={cn(
                    "px-3 py-2 cursor-pointer flex items-center justify-between",
                    currentSessionId === session.id ? "bg-gray-700" : "hover:bg-gray-700/50"
                  )}
                  onClick={() => {
                    setCurrentSessionId(session.id);
                    setShowSessions(false);
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "w-2 h-2 rounded-full",
                      session.is_active ? "bg-green-500" : "bg-gray-600"
                    )} />
                    <span className="text-sm font-mono text-gray-300">{session.id}</span>
                  </div>
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
              ))
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
            <MessageBubble key={i} message={msg} />
          ))}

          {currentResponse.length > 0 && (
            <div className="text-gray-300">
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
          <div className="flex gap-2">
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
                  ? `Ask ${role === 'dev' ? 'for code help' : 'about markets'}...`
                  : "Connecting..."
              }
              disabled={!isConnected || isLoading || !!pendingPermission || !currentSessionId}
              className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 text-sm"
            />
            {isLoading ? (
              <Button onClick={stopResponse} variant="destructive" size="sm">
                Stop
              </Button>
            ) : (
              <Button
                onClick={sendMessage}
                disabled={!isConnected || !input.trim() || !!pendingPermission || !currentSessionId}
                size="sm"
              >
                Send
              </Button>
            )}
          </div>
        </div>
      </SheetContent>

      {/* Settings Modal */}
      <SettingsModal open={showSettings} onOpenChange={setShowSettings} />

      {/* Status Modal */}
      <StatusModal open={showStatus} onOpenChange={setShowStatus} />
    </Sheet>
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
