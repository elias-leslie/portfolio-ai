'use client'

import { useEffect, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useJennyChat } from '@/lib/hooks/usePortfolio'
import { cn } from '@/lib/utils'

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

const SESSION_KEY = 'portfolio-ai:jenny-chat:session'
const HISTORY_KEY = 'portfolio-ai:jenny-chat:history'
const MAX_STORED_MESSAGES = 100
const MAX_MESSAGE_LENGTH = 5000

function loadStoredMessages(): ChatMessage[] {
  if (typeof window === 'undefined') {
    return []
  }
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed
      .filter(
        (message): message is ChatMessage =>
          typeof message === 'object' &&
          message !== null &&
          (message.role === 'user' || message.role === 'assistant') &&
          typeof message.content === 'string',
      )
      .map((m) => ({
        ...m,
        timestamp: typeof m.timestamp === 'number' ? m.timestamp : Date.now(),
      }))
      .slice(-MAX_STORED_MESSAGES)
  } catch {
    return []
  }
}

export function JennyChatPanel({
  title = 'Chat with Jenny',
  description = 'Ask about your portfolio, retirement plan, account balances, or answer Jenny in free-form.',
}: {
  title?: string
  description?: string
}) {
  const chatMutation = useJennyChat()
  const [message, setMessage] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [lastResolvedCount, setLastResolvedCount] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    setSessionId(window.localStorage.getItem(SESSION_KEY))
    setMessages(loadStoredMessages())
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    if (sessionId) {
      window.localStorage.setItem(SESSION_KEY, sessionId)
    }
  }, [sessionId])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    try {
      const capped = messages.slice(-MAX_STORED_MESSAGES)
      window.localStorage.setItem(HISTORY_KEY, JSON.stringify(capped))
    } catch {
      // localStorage full — clear old history and retry
      try {
        window.localStorage.removeItem(HISTORY_KEY)
      } catch {
        // ignore
      }
    }
  }, [messages])

  const handleSend = async () => {
    const trimmed = message.trim().slice(0, MAX_MESSAGE_LENGTH)
    if (!trimmed || chatMutation.isPending) {
      return
    }
    setErrorMessage(null)
    try {
      const response = await chatMutation.mutateAsync({
        message: trimmed,
        sessionId,
      })
      const now = Date.now()
      setSessionId(response.sessionId)
      setMessages((current) => [
        ...current,
        { role: 'user', content: trimmed, timestamp: now },
        { role: 'assistant', content: response.reply, timestamp: Date.now() },
      ])
      setMessage('')
      setLastResolvedCount(response.resolvedQuestions.length)
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : 'Jenny could not process that message right now.',
      )
    }
  }

  return (
    <SectionCard
      variant="surface"
      title={title}
      description={description}
      className="overflow-hidden"
      contentClassName="grid gap-4"
      actions={
        <Badge variant={chatMutation.isPending ? 'warning' : 'secondary'}>
          {chatMutation.isPending ? 'Jenny is thinking' : 'Portfolio-wide context'}
        </Badge>
      }
    >
      <div className="grid gap-4">
        {messages.length === 0 ? (
          <div className="rounded-2xl border border-border/40 bg-surface/70 px-4 py-3 text-sm text-text-muted">
            Try: &quot;What does Jenny think about AMD?&quot;, &quot;How much cash is in our IRA?&quot;, or &quot;I want to retire at 60.&quot;
          </div>
        ) : (
          <div className="max-h-[26rem] space-y-3 overflow-y-auto pr-1">
            {messages.map((entry) => (
              <div
                key={`${entry.role}-${entry.timestamp ?? 0}`}
                className={cn(
                  'rounded-2xl border px-4 py-3 text-sm',
                  entry.role === 'user'
                    ? 'border-primary/20 bg-primary/5 text-text'
                    : 'border-border/40 bg-surface-muted/20 text-text',
                )}
              >
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-muted">
                  {entry.role === 'user' ? 'You' : 'Jenny'}
                </p>
                <p className="whitespace-pre-wrap">{entry.content}</p>
              </div>
            ))}
          </div>
        )}

        {lastResolvedCount > 0 ? (
          <div className="rounded-2xl border border-gain/30 bg-gain/10 px-4 py-3 text-sm text-text">
            Jenny reconciled {lastResolvedCount} question{lastResolvedCount === 1 ? '' : 's'} from your last message.
          </div>
        ) : null}

        {errorMessage ? (
          <div className="rounded-2xl border border-loss/30 bg-loss/10 px-4 py-3 text-sm text-text">
            Jenny could not reply yet. {errorMessage}
          </div>
        ) : null}

        <div className="space-y-3">
          <Textarea
            value={message}
            onChange={(event) => {
              setMessage(event.target.value)
              if (errorMessage) {
                setErrorMessage(null)
              }
            }}
            placeholder="Ask anything about Portfolio-AI, or answer Jenny in plain English."
            rows={3}
          />
          <div className="flex justify-end">
            <Button
              onClick={() => void handleSend()}
              disabled={chatMutation.isPending || !message.trim()}
            >
              {chatMutation.isPending ? 'Sending...' : 'Send to Jenny'}
            </Button>
          </div>
        </div>
      </div>
    </SectionCard>
  )
}
