'use client';
/* eslint-disable react-hooks/preserve-manual-memoization */
/* eslint-disable react-hooks/set-state-in-effect */

import { useState, useRef, useEffect, useCallback } from 'react';
import { toCamelCaseKeys } from '@/lib/api/client';

// Message types from Claude's stream-json output
interface ContentBlock {
  type: 'text' | 'tool_use' | 'tool_result' | 'thinking';
  text?: string | null;
  toolName?: string | null;
  toolInput?: Record<string, unknown> | null;
  toolUseId?: string | null;
  isError?: boolean;
}

interface StreamMessage {
  type: 'assistant' | 'user' | 'system' | 'result';
  content: ContentBlock[];
  model?: string | null;
  stopReason?: string | null;
  sessionId?: string | null;
}

interface PermissionRequest {
  toolName: string;
  toolInput: Record<string, unknown>;
}

interface WebSocketMessage {
  type: 'stream' | 'done' | 'error' | 'pong' | 'permission_request' | 'interrupt_ack';
  data?: StreamMessage;
  message?: string;
  toolName?: string;
  toolInput?: Record<string, unknown>;
  success?: boolean;
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  blocks?: ContentBlock[];
  timestamp: Date;
}

interface ChatPanelProps {
  sessionId: string;
  serverUrl?: string;
}

// Get default WebSocket URL
// Use nginx proxy path /dev-companion/ for SSL termination
const getDefaultWsUrl = () => {
  if (typeof window === 'undefined') return 'ws://localhost:9999';
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsProtocol}//${window.location.host}/dev-companion`;
};

export default function ChatPanel({ sessionId, serverUrl }: ChatPanelProps) {
  // Use provided serverUrl or derive from current protocol
  const effectiveServerUrl = serverUrl || getDefaultWsUrl();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [currentResponse, setCurrentResponse] = useState<ContentBlock[]>([]);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [pendingPermission, setPendingPermission] = useState<PermissionRequest | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentResponseRef = useRef<ContentBlock[]>([]);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const connectRef = useRef<(() => void) | undefined>(undefined); // Ref for reconnect (avoids forward reference)
  const httpBaseUrl = effectiveServerUrl.replace('ws://', 'http://').replace('wss://', 'https://');

  // Keep ref in sync with state
  useEffect(() => {
    currentResponseRef.current = currentResponse;
  }, [currentResponse]);

  // Load history when session changes
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const res = await fetch(`${httpBaseUrl}/sessions/${sessionId}/history`);
        if (res.ok) {
          const data = await res.json();
          const loadedMessages: ChatMessage[] = data.messages.map((msg: { role: string; content: string; createdAt: string }) => ({
            role: msg.role as 'user' | 'assistant' | 'system',
            content: msg.content,
            timestamp: new Date(msg.createdAt),
          }));
          setMessages(loadedMessages);
        }
      } catch (err) {
        console.error('Failed to load history:', err);
      }
    };

    // Reset state for new session
    setMessages([]);
    setCurrentResponse([]);
    setIsLoading(false);

    loadHistory();
  }, [sessionId, httpBaseUrl]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentResponse]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Don't reconnect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    console.log(`Connecting to ${effectiveServerUrl}/ws/${sessionId}`);
    const ws = new WebSocket(`${effectiveServerUrl}/ws/${sessionId}`);

    ws.onopen = () => {
      setIsConnected(true);
      setConnectionError(null);
      console.log('WebSocket connected to:', ws.url);
    };

    ws.onclose = (event) => {
      setIsConnected(false);
      console.log('WebSocket disconnected:', event.code, event.reason);
      wsRef.current = null;
      // Attempt reconnect after 3 seconds (use ref to avoid forward reference)
      reconnectTimeoutRef.current = setTimeout(() => connectRef.current?.(), 3000);
    };

    ws.onerror = () => {
      // Note: onerror doesn't provide useful info, the error details come in onclose
      setConnectionError(`Failed to connect to ${ws.url}`);
    };

    ws.onmessage = (event) => {
      const msg: WebSocketMessage = toCamelCaseKeys(JSON.parse(event.data));
      // Capture timestamp once at event time (avoids render-time object creation)
      const eventTime = new Date();

      switch (msg.type) {
        case 'stream':
          if (msg.data) {
            // Accumulate content blocks
            setCurrentResponse(prev => [...prev, ...msg.data!.content]);
          }
          break;

        case 'done':
          // Finalize the response using ref for latest value
          const blocks = currentResponseRef.current;
          if (blocks.length > 0) {
            setMessages(prev => [
              ...prev,
              {
                role: 'assistant',
                content: blocksToText(blocks),
                blocks: blocks,
                timestamp: eventTime,
              },
            ]);
          }
          setCurrentResponse([]);
          setIsLoading(false);
          break;

        case 'error':
          setMessages(prev => [
            ...prev,
            {
              role: 'system',
              content: `Error: ${msg.message}`,
              timestamp: eventTime,
            },
          ]);
          setIsLoading(false);
          setPendingPermission(null);
          break;

        case 'permission_request':
          // Show permission prompt to user
          if (msg.toolName && msg.toolInput) {
            // Deep copy to prevent external mutation
            setPendingPermission({
              toolName: msg.toolName,
              toolInput: JSON.parse(JSON.stringify(msg.toolInput)),
            });
          }
          break;

        case 'interrupt_ack':
          // Interrupt acknowledged
          setPendingPermission(null);
          break;
      }
    };

    wsRef.current = ws;
  }, [sessionId, effectiveServerUrl]);

  // Keep connectRef in sync for reconnection
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  // Connect on mount, cleanup on unmount
  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  // Send message
  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || isLoading) return;

    const message = input.trim();
    const sendTime = new Date(); // Capture before state updates
    setInput('');
    setIsLoading(true);

    // Add user message to chat
    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        content: message,
        timestamp: sendTime,
      },
    ]);

    // Send to server
    wsRef.current.send(JSON.stringify({
      type: 'message',
      content: message,
    }));
  };

  // Stop/interrupt current response
  const stopResponse = () => {
    if (!wsRef.current || !isLoading) return;

    wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
    setIsLoading(false);
    setPendingPermission(null);
  };

  // Handle permission response
  const handlePermissionResponse = (allowed: boolean) => {
    if (!wsRef.current || !pendingPermission) return;

    const responseTime = new Date(); // Capture before state updates
    wsRef.current.send(JSON.stringify({
      type: 'permission_response',
      allowed,
    }));

    // Add to messages for visibility
    setMessages(prev => [
      ...prev,
      {
        role: 'system',
        content: `Permission ${allowed ? 'ALLOWED' : 'DENIED'} for: ${pendingPermission.toolName}`,
        timestamp: responseTime,
      },
    ]);

    setPendingPermission(null);
  };

  // Handle key press
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-bg text-text">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-gain' : 'bg-loss'}`} />
          <span className="text-sm text-text-muted">
            Session: {sessionId}
          </span>
          {connectionError && (
            <span className="text-xs text-loss" title={connectionError}>
              (reconnecting...)
            </span>
          )}
        </div>
        {isLoading && (
          <span className="text-sm text-primary animate-pulse">Claude is thinking...</span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-sm">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {/* Current streaming response */}
        {currentResponse.length > 0 && (
          <div className="text-text">
            {currentResponse.map((block, i) => (
              <ContentBlockView key={i} block={block} />
            ))}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Permission Request Modal */}
      {pendingPermission && (
        <div className="border-t border-warning bg-warning/30 p-4">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 text-2xl">&#9888;</div>
            <div className="flex-1">
              <h4 className="font-semibold text-warning mb-2">
                Permission Required
              </h4>
              <p className="text-sm text-warning mb-2">
                Claude wants to use: <span className="font-mono font-bold">{pendingPermission.toolName}</span>
              </p>
              {pendingPermission.toolInput && Object.keys(pendingPermission.toolInput).length > 0 && (
                <div className="bg-surface/50 rounded p-2 mb-3 max-h-32 overflow-y-auto">
                  <pre className="text-xs text-text whitespace-pre-wrap font-mono">
                    {JSON.stringify(pendingPermission.toolInput, null, 2)}
                  </pre>
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => handlePermissionResponse(true)}
                  className="px-4 py-2 bg-gain text-text-inverted rounded hover:bg-gain-strong font-medium"
                >
                  Allow
                </button>
                <button
                  onClick={() => handlePermissionResponse(false)}
                  className="px-4 py-2 bg-loss text-text-inverted rounded hover:bg-loss-strong font-medium"
                >
                  Deny
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-border p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={pendingPermission ? "Waiting for permission response..." : isConnected ? "Type a message..." : "Connecting..."}
            disabled={!isConnected || isLoading || !!pendingPermission}
            className="flex-1 bg-surface border border-border-subtle rounded px-3 py-2 text-text placeholder-text-muted focus:outline-none focus:border-primary disabled:opacity-50"
          />
          {isLoading ? (
            <button
              onClick={stopResponse}
              className="px-4 py-2 bg-loss text-text-inverted rounded hover:bg-loss-strong"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={sendMessage}
              disabled={!isConnected || !input.trim() || !!pendingPermission}
              className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Helper to convert blocks to plain text
function blocksToText(blocks: ContentBlock[]): string {
  return blocks
    .map(block => {
      if (block.type === 'text' && block.text) return block.text;
      if (block.type === 'tool_use') return `[Tool: ${block.toolName}]`;
      if (block.type === 'tool_result') return `[Result: ${block.text}]`;
      return '';
    })
    .join('');
}

// Message bubble component
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 ${
          isUser
            ? 'bg-primary text-primary-foreground'
            : isSystem
            ? 'bg-warning/50 text-warning border border-warning'
            : 'bg-surface text-text'
        }`}
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

// Content block renderer
function ContentBlockView({ block }: { block: ContentBlock }) {
  switch (block.type) {
    case 'text':
      return <div className="whitespace-pre-wrap">{block.text}</div>;

    case 'tool_use':
      return (
        <div className="my-2 p-2 bg-surface-muted/50 rounded border border-border animate-pulse">
          <div className="text-xs text-primary mb-1 flex items-center gap-2">
            <span className="inline-block w-2 h-2 bg-primary rounded-full animate-ping" />
            Running: {block.toolName}
          </div>
          {block.toolInput && (
            <pre className="text-xs text-text-muted overflow-x-auto max-h-20">
              {typeof block.toolInput === 'object'
                ? JSON.stringify(block.toolInput, null, 2).slice(0, 200)
                : String(block.toolInput).slice(0, 200)}
            </pre>
          )}
        </div>
      );

    case 'tool_result':
      return (
        <div className={`my-2 p-2 rounded border ${block.isError ? 'bg-loss/30 border-loss' : 'bg-surface-muted/30 border-border'}`}>
          <div className="text-xs text-text-muted mb-1">Result:</div>
          <pre className="text-xs overflow-x-auto whitespace-pre-wrap">{block.text}</pre>
        </div>
      );

    case 'thinking':
      return (
        <div className="my-2 p-2 bg-accent/30 rounded border border-accent">
          <div className="text-xs text-accent mb-1">Thinking...</div>
          <div className="text-xs text-text-muted italic">{block.text}</div>
        </div>
      );

    default:
      return null;
  }
}
