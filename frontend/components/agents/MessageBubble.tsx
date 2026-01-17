'use client'

import { Diamond, Star } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChatMessage, ContentBlock } from './wsHandlers'

export function ContentBlockView({ block }: { block: ContentBlock }) {
  switch (block.type) {
    case 'text':
      return <div className="whitespace-pre-wrap">{block.text}</div>

    case 'tool_use':
      return (
        <div className="my-2 p-2 bg-surface-muted/50 rounded border border-border animate-pulse">
          <div className="text-xs text-primary mb-1 flex items-center gap-2">
            <span className="inline-block w-2 h-2 bg-primary rounded-full animate-ping" />
            Running: {block.toolName}
          </div>
          {block.toolInput && (
            <pre className="text-xs text-text-muted overflow-x-auto max-h-16">
              {typeof block.toolInput === 'object'
                ? JSON.stringify(block.toolInput, null, 2).slice(0, 150)
                : String(block.toolInput).slice(0, 150)}
            </pre>
          )}
        </div>
      )

    case 'tool_result':
      return (
        <div
          className={cn(
            'my-2 p-2 rounded border',
            block.isError
              ? 'bg-loss/30 border-loss'
              : 'bg-surface-muted/30 border-border',
          )}
        >
          <div className="text-xs text-text-muted mb-1">Result:</div>
          <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
            {block.text}
          </pre>
        </div>
      )

    case 'thinking':
      return (
        <div className="my-2 p-2 bg-accent/30 rounded border border-accent">
          <div className="text-xs text-accent mb-1">Thinking...</div>
          <div className="text-xs text-text-muted italic">{block.text}</div>
        </div>
      )

    default:
      return null
  }
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={cn(
          'max-w-[85%] rounded-lg px-3 py-2 text-sm',
          isUser
            ? 'bg-primary text-primary-foreground'
            : isSystem
              ? 'bg-warning/50 text-warning border border-warning'
              : 'bg-surface text-text',
        )}
      >
        {/* Agent attribution icon */}
        {message.agent && !isUser && (
          <span
            className="inline-block mb-1 mr-1"
            title={message.agent === 'claude' ? 'Claude' : 'Gemini'}
          >
            {message.agent === 'claude' ? (
              <Diamond className="h-4 w-4 text-primary inline" />
            ) : (
              <Star className="h-4 w-4 text-gain inline" />
            )}
          </span>
        )}
        {message.blocks ? (
          message.blocks.map((block, i) => (
            <ContentBlockView key={i} block={block} />
          ))
        ) : (
          <div className="whitespace-pre-wrap">{message.content}</div>
        )}
        <div className="text-xs opacity-50 mt-1">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
