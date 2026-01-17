/**
 * WebSocket Message Handlers for Agent Panel
 *
 * Extracted handler functions for WebSocket messages in roundtable/single agent modes.
 */

import { toCamelCaseKeys } from '@/lib/api/client'
import type { AgentProvider } from './AgentSelector'
import type { LLMProvider } from './SettingsModal'

// Types from AgentPanel
export interface ContentBlock {
  type: 'text' | 'tool_use' | 'tool_result' | 'thinking'
  text?: string | null
  toolName?: string | null
  toolInput?: Record<string, unknown> | null
  toolUseId?: string | null
  isError?: boolean
}

export interface StreamMessage {
  type: 'assistant' | 'user' | 'system' | 'result'
  content: ContentBlock[]
  model?: string | null
  stopReason?: string | null
  sessionId?: string | null
}

export interface PermissionRequest {
  toolName: string
  toolInput: Record<string, unknown>
}

export interface WebSocketMessage {
  type:
    | 'stream'
    | 'done'
    | 'error'
    | 'pong'
    | 'permission_request'
    | 'interrupt_ack'
    | 'provider'
    | 'agent_start'
    | 'agent_done'
    | 'discussion_start'
    | 'discussion_round'
  data?: StreamMessage
  message?: string
  toolName?: string
  toolInput?: Record<string, unknown>
  success?: boolean
  name?: string
  agent?: 'claude' | 'gemini'
  round?: number
  reason?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'evidence'
  content: string
  blocks?: ContentBlock[]
  timestamp: Date
  agent?: 'claude' | 'gemini'
  evidence?: EvidenceData
}

export interface EvidenceData {
  featureId: string
  criterionId: string
  version: number
  consoleErrors: number
  networkFailures: number
  url: string
}

/** Context for handler state management */
export interface HandlerContext {
  currentResponseRef: React.MutableRefObject<ContentBlock[]>
  currentRespondingAgent: 'claude' | 'gemini' | null
  agentProvider: AgentProvider
  setCurrentResponse: (
    updater: ContentBlock[] | ((prev: ContentBlock[]) => ContentBlock[]),
  ) => void
  setCurrentRespondingAgent: (agent: 'claude' | 'gemini' | null) => void
  setMessages: (updater: (prev: ChatMessage[]) => ChatMessage[]) => void
  setIsLoading: (loading: boolean) => void
  setPendingPermission: (perm: PermissionRequest | null) => void
  setActiveProvider: (provider: LLMProvider) => void
}

/** Handle incoming stream message - append content blocks */
export function handleStreamMessage(
  msg: WebSocketMessage,
  ctx: HandlerContext,
): void {
  if (msg.data?.content) {
    ctx.setCurrentResponse((prev) => [...prev, ...msg.data!.content])
  }
}

/** Handle agent_start - track which agent is responding in roundtable mode */
export function handleAgentStart(
  msg: WebSocketMessage,
  ctx: HandlerContext,
): void {
  if (msg.agent) {
    ctx.setCurrentRespondingAgent(msg.agent)
  }
}

/** Handle agent_done - save current agent's response with attribution */
export function handleAgentDone(
  msg: WebSocketMessage,
  ctx: HandlerContext,
): void {
  const blocks = ctx.currentResponseRef.current
  if (blocks.length > 0) {
    ctx.setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: blocksToText(blocks),
        blocks: blocks,
        timestamp: new Date(),
        agent: msg.agent,
      },
    ])
  }
  ctx.setCurrentResponse([])
  ctx.setCurrentRespondingAgent(null)
}

/** Handle discussion_start - show system message that discussion is starting */
export function handleDiscussionStart(ctx: HandlerContext): void {
  ctx.setMessages((prev) => [
    ...prev,
    {
      role: 'system',
      content: 'Agents disagree — starting discussion...',
      timestamp: new Date(),
    },
  ])
}

/** Handle discussion_round - show which round we're in */
export function handleDiscussionRound(
  msg: WebSocketMessage,
  ctx: HandlerContext,
): void {
  if (msg.round) {
    ctx.setMessages((prev) => [
      ...prev,
      {
        role: 'system',
        content: `Discussion round ${msg.round}`,
        timestamp: new Date(),
      },
    ])
  }
}

/** Handle done - finalize response and reset state */
export function handleDone(ctx: HandlerContext): void {
  const blocks = ctx.currentResponseRef.current
  if (blocks.length > 0) {
    const agent =
      ctx.currentRespondingAgent ||
      (ctx.agentProvider !== 'both' ? ctx.agentProvider : undefined)
    ctx.setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: blocksToText(blocks),
        blocks: blocks,
        timestamp: new Date(),
        agent,
      },
    ])
  }
  ctx.setCurrentResponse([])
  ctx.setCurrentRespondingAgent(null)
  ctx.setIsLoading(false)
}

/** Handle error - show error message and reset state */
export function handleError(msg: WebSocketMessage, ctx: HandlerContext): void {
  ctx.setMessages((prev) => [
    ...prev,
    {
      role: 'system',
      content: `Error: ${msg.message}`,
      timestamp: new Date(),
    },
  ])
  ctx.setIsLoading(false)
  ctx.setPendingPermission(null)
  ctx.setCurrentRespondingAgent(null)
}

/** Handle permission_request - prompt user for tool approval */
export function handlePermissionRequest(
  msg: WebSocketMessage,
  ctx: HandlerContext,
): void {
  if (msg.toolName && msg.toolInput) {
    ctx.setPendingPermission({
      toolName: msg.toolName,
      toolInput: msg.toolInput,
    })
  }
}

/** Handle interrupt_ack - clear pending permission */
export function handleInterruptAck(ctx: HandlerContext): void {
  ctx.setPendingPermission(null)
}

/** Handle provider - server confirms which provider is active */
export function handleProviderConfirmation(
  msg: WebSocketMessage,
  ctx: HandlerContext,
): void {
  if (msg.name) {
    ctx.setActiveProvider(msg.name as LLMProvider)
  }
}

/** Convert content blocks to plain text */
export function blocksToText(blocks: ContentBlock[]): string {
  return blocks
    .map((block) => {
      if (block.type === 'text' && block.text) return block.text
      if (block.type === 'tool_use') return `[Tool: ${block.toolName}]`
      if (block.type === 'tool_result') return `[Result: ${block.text}]`
      return ''
    })
    .join('')
}

/** Parse raw WebSocket message event */
export function parseWebSocketMessage(event: MessageEvent): WebSocketMessage {
  return toCamelCaseKeys(JSON.parse(event.data))
}

/** Route message to appropriate handler based on type */
export function routeMessage(msg: WebSocketMessage, ctx: HandlerContext): void {
  switch (msg.type) {
    case 'stream':
      handleStreamMessage(msg, ctx)
      break
    case 'agent_start':
      handleAgentStart(msg, ctx)
      break
    case 'agent_done':
      handleAgentDone(msg, ctx)
      break
    case 'discussion_start':
      handleDiscussionStart(ctx)
      break
    case 'discussion_round':
      handleDiscussionRound(msg, ctx)
      break
    case 'done':
      handleDone(ctx)
      break
    case 'error':
      handleError(msg, ctx)
      break
    case 'permission_request':
      handlePermissionRequest(msg, ctx)
      break
    case 'interrupt_ack':
      handleInterruptAck(ctx)
      break
    case 'provider':
      handleProviderConfirmation(msg, ctx)
      break
  }
}
