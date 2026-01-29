// Message types from Claude's stream-json output
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
  data?: StreamMessage
  message?: string
  toolName?: string
  toolInput?: Record<string, unknown>
  success?: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  blocks?: ContentBlock[]
  timestamp: Date
}

export interface ChatPanelProps {
  sessionId: string
  serverUrl?: string
}
