import type { ContentBlock } from './types'

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
            <pre className="text-xs text-text-muted overflow-x-auto max-h-20">
              {typeof block.toolInput === 'object'
                ? JSON.stringify(block.toolInput, null, 2).slice(0, 200)
                : String(block.toolInput).slice(0, 200)}
            </pre>
          )}
        </div>
      )

    case 'tool_result':
      return (
        <div
          className={`my-2 p-2 rounded border ${block.isError ? 'bg-loss/30 border-loss' : 'bg-surface-muted/30 border-border'}`}
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
