'use client'
/* eslint-disable react-hooks/preserve-manual-memoization */
/* eslint-disable react-hooks/set-state-in-effect */

import { useEffect, useRef, useState } from 'react'
import { ContentBlockView } from './ContentBlockView'
import { MessageBubble } from './MessageBubble'
import { PermissionModal } from './PermissionModal'
import type { ChatMessage, ChatPanelProps } from './types'
import { useWebSocket } from './useWebSocket'
import { getDefaultWsUrl } from './utils'

export default function ChatPanel({ sessionId, serverUrl }: ChatPanelProps) {
  const effectiveServerUrl = serverUrl || getDefaultWsUrl()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const httpBaseUrl = effectiveServerUrl
    .replace('ws://', 'http://')
    .replace('wss://', 'https://')

  const {
    isConnected,
    connectionError,
    currentResponse,
    pendingPermission,
    sendMessage: wsSendMessage,
    stopResponse,
    handlePermissionResponse,
    setMessagesCallback,
  } = useWebSocket(sessionId, effectiveServerUrl)

  // Provide messages setter to WebSocket hook
  useEffect(() => {
    setMessagesCallback(setMessages)
  }, [setMessagesCallback])

  // Load history when session changes
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const res = await fetch(`${httpBaseUrl}/sessions/${sessionId}/history`)
        if (res.ok) {
          const data = await res.json()
          const loadedMessages: ChatMessage[] = data.messages.map(
            (msg: { role: string; content: string; createdAt: string }) => ({
              role: msg.role as 'user' | 'assistant' | 'system',
              content: msg.content,
              timestamp: new Date(msg.createdAt),
            }),
          )
          setMessages(loadedMessages)
        }
      } catch (err) {
        console.error('Failed to load history:', err)
      }
    }

    // Reset state for new session
    setMessages([])
    setIsLoading(false)
    loadHistory()
  }, [sessionId, httpBaseUrl])

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentResponse])

  // Send message handler
  const handleSendMessage = () => {
    if (!input.trim() || isLoading) return

    const message = input.trim()
    const sendTime = new Date()
    setInput('')
    setIsLoading(true)

    // Add user message to chat
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content: message,
        timestamp: sendTime,
      },
    ])

    // Send to server
    if (!wsSendMessage(message)) {
      setIsLoading(false)
    }
  }

  // Stop handler
  const handleStop = () => {
    stopResponse()
    setIsLoading(false)
  }

  // Handle key press
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Update loading state when response completes
  useEffect(() => {
    if (currentResponse.length === 0 && isLoading) {
      setIsLoading(false)
    }
  }, [currentResponse, isLoading])

  return (
    <div className="flex flex-col h-full bg-bg text-text">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${isConnected ? 'bg-gain' : 'bg-loss'}`}
          />
          <span className="text-sm text-text-muted">Session: {sessionId}</span>
          {connectionError && (
            <span className="text-xs text-loss" title={connectionError}>
              (reconnecting...)
            </span>
          )}
        </div>
        {isLoading && (
          <span className="text-sm text-primary animate-pulse">
            Claude is thinking...
          </span>
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
        <PermissionModal
          permission={pendingPermission}
          onRespond={handlePermissionResponse}
        />
      )}

      {/* Input */}
      <div className="border-t border-border p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              pendingPermission
                ? 'Waiting for permission response...'
                : isConnected
                  ? 'Type a message...'
                  : 'Connecting...'
            }
            disabled={!isConnected || isLoading || !!pendingPermission}
            className="flex-1 bg-surface border border-border-subtle rounded px-3 py-2 text-text placeholder-text-muted focus:outline-none focus:border-primary disabled:opacity-50"
          />
          {isLoading ? (
            <button
              onClick={handleStop}
              className="px-4 py-2 bg-loss text-text-inverted rounded hover:bg-loss-strong"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={handleSendMessage}
              disabled={!isConnected || !input.trim() || !!pendingPermission}
              className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
