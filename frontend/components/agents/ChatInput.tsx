'use client'

import { Button } from '@/components/ui/button'
import {
  type AgentProvider,
  AgentSelector,
  type RoundtableOrder,
} from './AgentSelector'
import { type AgentMode, ModeSelector } from './ModeSelector'

interface ChatInputProps {
  input: string
  onInputChange: (value: string) => void
  onSend: () => void
  onStop: () => void
  onKeyPress: (e: React.KeyboardEvent) => void
  isConnected: boolean
  isLoading: boolean
  hasPendingPermission: boolean
  hasSession: boolean
  agentMode: AgentMode
  agentProvider: AgentProvider
  roundtableOrder: RoundtableOrder
  maxTurns: number
  onAgentProviderChange: (value: AgentProvider) => void
  onAgentModeChange: (value: AgentMode) => void
  onRoundtableOrderChange: (value: RoundtableOrder) => void
  onMaxTurnsChange: (value: number) => void
}

function getInputPlaceholder(
  hasPendingPermission: boolean,
  hasSession: boolean,
  isConnected: boolean,
  agentMode: AgentMode,
): string {
  if (hasPendingPermission) return 'Waiting for permission...'
  if (!hasSession) return 'Create a session first...'
  if (!isConnected) return 'Connecting...'
  return `Ask ${agentMode === 'dev' ? 'for code help' : 'about markets'}...`
}

export function ChatInput({
  input,
  onInputChange,
  onSend,
  onStop,
  onKeyPress,
  isConnected,
  isLoading,
  hasPendingPermission,
  hasSession,
  agentMode,
  agentProvider,
  roundtableOrder,
  maxTurns,
  onAgentProviderChange,
  onAgentModeChange,
  onRoundtableOrderChange,
  onMaxTurnsChange,
}: ChatInputProps) {
  const placeholder = getInputPlaceholder(
    hasPendingPermission,
    hasSession,
    isConnected,
    agentMode,
  )
  const isDisabled =
    !isConnected || isLoading || hasPendingPermission || !hasSession

  return (
    <div className="border-t border-border p-4">
      {/* suppressHydrationWarning on container to handle browser extensions (Dashlane) */}
      <div className="flex gap-2 items-center" suppressHydrationWarning>
        <input
          type="text"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyPress={onKeyPress}
          placeholder={placeholder}
          disabled={isDisabled}
          className="flex-1 bg-surface border border-border-subtle rounded px-3 py-2 text-text placeholder-text-muted focus:outline-none focus:border-primary disabled:opacity-50 text-sm"
          suppressHydrationWarning
        />
        {/* Agent & Mode selectors - always visible for quick toggle */}
        <AgentSelector
          value={agentProvider}
          onChange={onAgentProviderChange}
          disabled={!isConnected}
          roundtableOrder={roundtableOrder}
          onRoundtableOrderChange={onRoundtableOrderChange}
          maxTurns={maxTurns}
          onMaxTurnsChange={onMaxTurnsChange}
        />
        <ModeSelector
          value={agentMode}
          onChange={onAgentModeChange}
          disabled={!isConnected}
        />
        {isLoading ? (
          <Button onClick={onStop} variant="destructive" size="sm">
            Stop
          </Button>
        ) : (
          <Button
            onClick={onSend}
            disabled={
              !isConnected ||
              !input.trim() ||
              hasPendingPermission ||
              !hasSession
            }
            size="sm"
          >
            Send
          </Button>
        )}
      </div>
    </div>
  )
}
