'use client'

import { Diamond, Star } from 'lucide-react'
import { ContentBlockView, MessageBubble } from './MessageBubble'
import { EvidenceMessageBubble } from './EvidenceMessageBubble'
import type { ChatMessage, ContentBlock } from './wsHandlers'

// Magic string constants for SummitFlow evidence viewer URL
const SUMMITFLOW_LOCAL_URL = 'http://localhost:3001'
const SUMMITFLOW_PROD_URL = 'https://dev.summitflow.dev'
const SUMMITFLOW_EVIDENCE_TAB = '/projects/portfolio-ai?tab=evidence'

function getSummitFlowBaseUrl(): string {
  if (typeof window === 'undefined') return SUMMITFLOW_LOCAL_URL
  const host = window.location.hostname
  const isLocal = host === 'localhost' || host === '127.0.0.1'
  return (
    process.env.NEXT_PUBLIC_SUMMITFLOW_URL ||
    (isLocal ? SUMMITFLOW_LOCAL_URL : SUMMITFLOW_PROD_URL)
  )
}

interface AgentMessageListProps {
  messages: ChatMessage[]
  currentResponse: ContentBlock[]
  currentRespondingAgent: 'claude' | 'gemini' | null
  messagesEndRef: React.RefObject<HTMLDivElement | null>
}

export function AgentMessageList({
  messages,
  currentResponse,
  currentRespondingAgent,
  messagesEndRef,
}: AgentMessageListProps) {
  const handleViewEvidence = () => {
    window.open(
      `${getSummitFlowBaseUrl()}${SUMMITFLOW_EVIDENCE_TAB}`,
      '_blank',
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-sm">
      {messages.map((msg, i) =>
        msg.role === 'evidence' && msg.evidence ? (
          <EvidenceMessageBubble
            key={i}
            message={msg}
            onViewEvidence={handleViewEvidence}
          />
        ) : (
          <MessageBubble key={i} message={msg} />
        ),
      )}

      {currentResponse.length > 0 && (
        <div className="text-text">
          {currentRespondingAgent && (
            <span
              className="inline-block mb-1 mr-1"
              title={currentRespondingAgent === 'claude' ? 'Claude' : 'Gemini'}
            >
              {currentRespondingAgent === 'claude' ? (
                <Diamond className="h-4 w-4 text-primary inline" />
              ) : (
                <Star className="h-4 w-4 text-gain inline" />
              )}
            </span>
          )}
          {currentResponse.map((block, i) => (
            <ContentBlockView key={i} block={block} />
          ))}
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  )
}
