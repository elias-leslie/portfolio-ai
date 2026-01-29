import { useCallback, useEffect, useRef, useState } from 'react'
import { toCamelCaseKeys } from '@/lib/api/client'
import type {
  ContentBlock,
  WebSocketMessage,
  PermissionRequest,
  ChatMessage,
} from './types'
import { blocksToText } from './utils'

export function useWebSocket(sessionId: string, wsUrl: string) {
  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [currentResponse, setCurrentResponse] = useState<ContentBlock[]>([])
  const [pendingPermission, setPendingPermission] =
    useState<PermissionRequest | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const currentResponseRef = useRef<ContentBlock[]>([])
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const connectRef = useRef<(() => void) | undefined>(undefined)
  const messagesCallbackRef = useRef<
    (updater: (prev: ChatMessage[]) => ChatMessage[]) => void
  >(() => {})

  // Keep ref in sync with state
  useEffect(() => {
    currentResponseRef.current = currentResponse
  }, [currentResponse])

  // Connect to WebSocket
  const connect = useCallback(() => {
    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    // Don't reconnect if already connected or connecting
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return
    }

    console.log(`Connecting to ${wsUrl}/ws/${sessionId}`)
    const ws = new WebSocket(`${wsUrl}/ws/${sessionId}`)

    ws.onopen = () => {
      setIsConnected(true)
      setConnectionError(null)
      console.log('WebSocket connected to:', ws.url)
    }

    ws.onclose = (event) => {
      setIsConnected(false)
      console.log('WebSocket disconnected:', event.code, event.reason)
      wsRef.current = null
      // Attempt reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(
        () => connectRef.current?.(),
        3000,
      )
    }

    ws.onerror = () => {
      setConnectionError(`Failed to connect to ${ws.url}`)
    }

    ws.onmessage = (event) => {
      const msg: WebSocketMessage = toCamelCaseKeys(JSON.parse(event.data))
      const eventTime = new Date()

      switch (msg.type) {
        case 'stream':
          if (msg.data?.content) {
            setCurrentResponse((prev) => [...prev, ...msg.data!.content])
          }
          break

        case 'done': {
          const blocks = currentResponseRef.current
          if (blocks.length > 0) {
            messagesCallbackRef.current((prev) => [
              ...prev,
              {
                role: 'assistant',
                content: blocksToText(blocks),
                blocks: blocks,
                timestamp: eventTime,
              },
            ])
          }
          setCurrentResponse([])
          break
        }

        case 'error':
          messagesCallbackRef.current((prev) => [
            ...prev,
            {
              role: 'system',
              content: `Error: ${msg.message}`,
              timestamp: eventTime,
            },
          ])
          setPendingPermission(null)
          break

        case 'permission_request':
          if (msg.toolName && msg.toolInput) {
            setPendingPermission({
              toolName: msg.toolName,
              toolInput: JSON.parse(JSON.stringify(msg.toolInput)),
            })
          }
          break

        case 'interrupt_ack':
          setPendingPermission(null)
          break
      }
    }

    wsRef.current = ws
  }, [sessionId, wsUrl])

  // Keep connectRef in sync for reconnection
  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  // Connect on mount, cleanup on unmount
  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  const sendMessage = useCallback((message: string) => {
    if (!wsRef.current) return false

    wsRef.current.send(
      JSON.stringify({
        type: 'message',
        content: message,
      }),
    )
    return true
  }, [])

  const stopResponse = useCallback(() => {
    if (!wsRef.current) return

    wsRef.current.send(JSON.stringify({ type: 'interrupt' }))
    setPendingPermission(null)
  }, [])

  const handlePermissionResponse = useCallback((allowed: boolean) => {
    if (!wsRef.current || !pendingPermission) return

    const responseTime = new Date()
    wsRef.current.send(
      JSON.stringify({
        type: 'permission_response',
        allowed,
      }),
    )

    messagesCallbackRef.current((prev) => [
      ...prev,
      {
        role: 'system',
        content: `Permission ${allowed ? 'ALLOWED' : 'DENIED'} for: ${pendingPermission.toolName}`,
        timestamp: responseTime,
      },
    ])

    setPendingPermission(null)
  }, [pendingPermission])

  return {
    isConnected,
    connectionError,
    currentResponse,
    pendingPermission,
    sendMessage,
    stopResponse,
    handlePermissionResponse,
    setMessagesCallback: (
      callback: (updater: (prev: ChatMessage[]) => ChatMessage[]) => void,
    ) => {
      messagesCallbackRef.current = callback
    },
  }
}
