'use client';

import { useRef, useCallback, useEffect } from 'react';
import type { MutableRefObject, Dispatch, SetStateAction } from 'react';
import {
  parseWebSocketMessage,
  routeMessage,
  type HandlerContext,
  type ContentBlock,
  type PermissionRequest,
} from '../wsHandlers';
import type { LLMProvider } from '../SettingsModal';
import type { AgentProvider, RoundtableOrder } from '../AgentSelector';
import type { ChatMessage } from '../wsHandlers';

export interface UseWebSocketConnectionOptions {
  wsUrl: string | null;
  currentSessionId: string | null;
  open: boolean;
  agentProvider: AgentProvider;
  roundtableOrder: RoundtableOrder;
  maxTurns: number;
  currentRespondingAgent: 'claude' | 'gemini' | null;
  currentResponseRef: MutableRefObject<ContentBlock[]>;
  setCurrentResponse: Dispatch<SetStateAction<ContentBlock[]>>;
  setCurrentRespondingAgent: Dispatch<SetStateAction<'claude' | 'gemini' | null>>;
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
  setPendingPermission: Dispatch<SetStateAction<PermissionRequest | null>>;
  setActiveProvider?: Dispatch<SetStateAction<LLMProvider>>;
  setIsConnected: Dispatch<SetStateAction<boolean>>;
  setConnectionError: Dispatch<SetStateAction<string | null>>;
}

export interface UseWebSocketConnectionReturn {
  wsRef: MutableRefObject<WebSocket | null>;
  connect: () => void;
  isConnected: boolean;
}

export function useWebSocketConnection({
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
  setActiveProvider,
  setIsConnected,
  setConnectionError,
}: UseWebSocketConnectionOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const intentionalCloseRef = useRef(false);
  const connectionGenRef = useRef(0);
  // Use a ref to store connect function for self-referencing in onclose
  const connectRef = useRef<() => void>(() => {});

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
      if (thisGeneration === connectionGenRef.current) {
        setIsConnected(true);
        setConnectionError(null);
        console.log('WebSocket opened, generation:', thisGeneration);
      }
    };

    ws.onclose = () => {
      // Only update state if this is still the current connection generation
      if (thisGeneration === connectionGenRef.current) {
        setIsConnected(false);
        wsRef.current = null;
        console.log('WebSocket closed, generation:', thisGeneration);
        // Only reconnect if this wasn't an intentional close
        if (open && !intentionalCloseRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => connectRef.current(), 3000);
        }
      } else {
        console.log('Ignoring stale onclose for generation:', thisGeneration, 'current:', connectionGenRef.current);
      }
    };

    ws.onerror = () => {
      setConnectionError(`Failed to connect to ${ws.url}`);
    };

    ws.onmessage = (event) => {
      const msg = parseWebSocketMessage(event);
      const ctx: HandlerContext = {
        currentResponseRef,
        currentRespondingAgent,
        agentProvider,
        setCurrentResponse,
        setCurrentRespondingAgent,
        setMessages,
        setIsLoading,
        setPendingPermission,
        setActiveProvider,
      };
      routeMessage(msg, ctx);
    };

    wsRef.current = ws;
  }, [
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
    setActiveProvider,
    setIsConnected,
    setConnectionError,
  ]);

  // Keep ref in sync with the latest connect function
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

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

  return {
    wsRef,
    connect,
  };
}
