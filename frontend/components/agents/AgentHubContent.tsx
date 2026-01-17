'use client'

import { AgentPanel } from './AgentPanel'

interface PageContext {
  path: string
  data?: Record<string, unknown>
}

interface AgentHubContentProps {
  pageContext: PageContext
}

/**
 * Standalone Agent Hub content for popup window.
 * Wraps AgentPanel in standalone mode (full-page, no fixed positioning).
 */
export function AgentHubContent({ pageContext }: AgentHubContentProps) {
  return (
    <AgentPanel
      open={true}
      onOpenChange={() => {
        // In standalone mode, closing means closing the popup window
        window.close()
      }}
      pageContext={pageContext}
      standalone={true}
    />
  )
}
