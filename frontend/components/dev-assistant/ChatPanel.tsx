'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

// Message types from Claude's stream-json output
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
  type: 'stream' | 'done' | 'error' | 'pong' | 'permission_request' | 'interrupt_ack';
  data?: StreamMessage;
  message?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
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

export default function ChatPanel({ sessionId, serverUrl = 'ws://localhost:9999' }: ChatPanelProps) {
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
  const httpBaseUrl = serverUrl.replace('ws://', 'http://').replace('wss://', 'https://');

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

    console.log(`Connecting to ${serverUrl}/ws/${sessionId}`);
    const ws = new WebSocket(`${serverUrl}/ws/${sessionId}`);

    ws.onopen = () => {
      setIsConnected(true);
      setConnectionError(null);
      console.log('WebSocket connected to:', ws.url);
    };

    ws.onclose = (event) => {
      setIsConnected(false);
      console.log('WebSocket disconnected:', event.code, event.reason);
      wsRef.current = null;
      // Attempt reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      // Note: onerror doesn't provide useful info, the error details come in onclose
      setConnectionError(`Failed to connect to ${ws.url}`);
    };

    ws.onmessage = (event) => {
      const msg: WebSocketMessage = JSON.parse(event.data);

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
                timestamp: new Date(),
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
              timestamp: new Date(),
            },
          ]);
          setIsLoading(false);
          setPendingPermission(null);
          break;

        case 'permission_request':
          // Show permission prompt to user
          if (msg.tool_name && msg.tool_input) {
            setPendingPermission({
              tool_name: msg.tool_name,
              tool_input: msg.tool_input,
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
  }, [sessionId, serverUrl]);

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
    setInput('');
    setIsLoading(true);

    // Add user message to chat
    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        content: message,
        timestamp: new Date(),
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

    wsRef.current.send(JSON.stringify({
      type: 'permission_response',
      allowed,
    }));

    // Add to messages for visibility
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

  // Handle key press
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-100">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-400">
            Session: {sessionId}
          </span>
          {connectionError && (
            <span className="text-xs text-red-400" title={connectionError}>
              (reconnecting...)
            </span>
          )}
        </div>
        {isLoading && (
          <span className="text-sm text-blue-400 animate-pulse">Claude is thinking...</span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-sm">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {/* Current streaming response */}
        {currentResponse.length > 0 && (
          <div className="text-gray-300">
            {currentResponse.map((block, i) => (
              <ContentBlockView key={i} block={block} />
            ))}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Permission Request Modal */}
      {pendingPermission && (
        <div className="border-t border-yellow-600 bg-yellow-900/30 p-4">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 text-2xl">&#9888;</div>
            <div className="flex-1">
              <h4 className="font-semibold text-yellow-200 mb-2">
                Permission Required
              </h4>
              <p className="text-sm text-yellow-100 mb-2">
                Claude wants to use: <span className="font-mono font-bold">{pendingPermission.tool_name}</span>
              </p>
              {pendingPermission.tool_input && Object.keys(pendingPermission.tool_input).length > 0 && (
                <div className="bg-gray-800/50 rounded p-2 mb-3 max-h-32 overflow-y-auto">
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">
                    {JSON.stringify(pendingPermission.tool_input, null, 2)}
                  </pre>
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => handlePermissionResponse(true)}
                  className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 font-medium"
                >
                  Allow
                </button>
                <button
                  onClick={() => handlePermissionResponse(false)}
                  className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 font-medium"
                >
                  Deny
                </button>
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
            placeholder={pendingPermission ? "Waiting for permission response..." : isConnected ? "Type a message..." : "Connecting..."}
            disabled={!isConnected || isLoading || !!pendingPermission}
            className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
          />
          {isLoading ? (
            <button
              onClick={stopResponse}
              className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={sendMessage}
              disabled={!isConnected || !input.trim() || !!pendingPermission}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
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
      if (block.type === 'tool_use') return `[Tool: ${block.tool_name}]`;
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
            ? 'bg-blue-600 text-white'
            : isSystem
            ? 'bg-yellow-900/50 text-yellow-200 border border-yellow-700'
            : 'bg-gray-800 text-gray-100'
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
        <div className="my-2 p-2 bg-gray-700/50 rounded border border-gray-600 animate-pulse">
          <div className="text-xs text-blue-400 mb-1 flex items-center gap-2">
            <span className="inline-block w-2 h-2 bg-blue-400 rounded-full animate-ping" />
            Running: {block.tool_name}
          </div>
          {block.tool_input && (
            <pre className="text-xs text-gray-400 overflow-x-auto max-h-20">
              {typeof block.tool_input === 'object'
                ? JSON.stringify(block.tool_input, null, 2).slice(0, 200)
                : String(block.tool_input).slice(0, 200)}
            </pre>
          )}
        </div>
      );

    case 'tool_result':
      return (
        <div className={`my-2 p-2 rounded border ${block.is_error ? 'bg-red-900/30 border-red-700' : 'bg-gray-700/30 border-gray-600'}`}>
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
