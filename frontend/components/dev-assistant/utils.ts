import type { ContentBlock } from './types'

// Get default WebSocket URL
// Use nginx proxy path /dev-companion/ for SSL termination
export const getDefaultWsUrl = () => {
  if (typeof window === 'undefined') return 'ws://localhost:9999'
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${wsProtocol}//${window.location.host}/dev-companion`
}

// Helper to convert blocks to plain text
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
