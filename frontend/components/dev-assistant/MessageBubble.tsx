import type { ChatMessage } from './types'
import { ContentBlockView } from './ContentBlockView'

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

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
