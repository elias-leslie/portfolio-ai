'use client'

import {
  Bot,
  ChevronRight,
  MessageSquare,
  RefreshCw,
  Users,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn, formatRelativeTime } from '@/lib/utils'
import { ProviderBadge } from './ProviderBadge'

interface SessionInfo {
  id: string
  agentType: string
  runType: string
  sessionType: string
  startedAt: string
  completedAt: string | null
  status: string
  provider: string | null
  model: string | null
  tokenCount: number
  parentRunId: string | null
  summary: string | null
}

// Dev Companion session format
interface DevCompanionSession {
  id: string
  workingDir: string
  createdAt: string
  updatedAt: string
  isActive: boolean
  metadata: Record<string, unknown>
  originalProvider?: string | null
  messageCount?: number
  description?: string | null
  participants?: string[]
}

function formatTokenCount(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}K`
  }
  return tokens.toString()
}

function SessionTypeBadge({ type }: { type: string }) {
  const config = {
    userSingleAgent: {
      icon: MessageSquare,
      label: 'User Chat',
      color: 'text-accent bg-accent/20',
    },
    userMultiAgent: {
      icon: Users,
      label: 'Roundtable',
      color: 'text-primary bg-primary/20',
    },
    agentAgentValidation: {
      icon: RefreshCw,
      label: 'Validation',
      color: 'text-warning bg-warning/20',
    },
    agentAutonomous: {
      icon: Bot,
      label: 'Automated',
      color: 'text-gain bg-gain/20',
    },
  }[type] || {
    icon: Bot,
    label: type,
    color: 'text-text-muted bg-surface-muted',
  }

  const Icon = config.icon

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
        config.color,
      )}
    >
      <Icon className="h-3 w-3" />
      {config.label}
    </span>
  )
}

interface SessionsListProps {
  serverUrl?: string
  onSelectSession?: (session: SessionInfo) => void
  maxHeight?: string
}

export function SessionsList({
  serverUrl = '',
  onSelectSession,
  maxHeight = '300px',
}: SessionsListProps) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSessions = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const res = await fetch(`${serverUrl}/api/agents/sessions?limit=20`)
        if (!res.ok) throw new Error('Failed to fetch sessions')
        const data = await res.json()
        setSessions(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sessions')
      } finally {
        setIsLoading(false)
      }
    }

    fetchSessions()
    // Refresh every minute
    const interval = setInterval(fetchSessions, 60 * 1000)
    return () => clearInterval(interval)
  }, [serverUrl])

  if (isLoading) {
    return (
      <div className="p-4 text-center text-text-muted text-sm">
        Loading sessions...
      </div>
    )
  }

  if (error) {
    return <div className="p-4 text-center text-loss text-sm">{error}</div>
  }

  if (sessions.length === 0) {
    return (
      <div className="p-4 text-center text-text-muted text-sm">
        No agent sessions yet
      </div>
    )
  }

  return (
    <div className="overflow-y-auto" style={{ maxHeight }}>
      {sessions.map((session) => (
        <div
          key={session.id}
          className={cn(
            'p-3 border-b border-border hover:bg-surface/50 cursor-pointer transition-colors',
            onSelectSession && 'group',
          )}
          onClick={() => onSelectSession?.(session)}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <SessionTypeBadge type={session.sessionType} />
                <span className="text-xs text-text-muted">
                  {formatRelativeTime(session.startedAt)}
                </span>
              </div>
              <div className="text-sm text-text font-medium truncate">
                {session.agentType}
              </div>
              {session.summary && (
                <div className="text-xs text-text-muted truncate mt-0.5">
                  {session.summary}
                </div>
              )}
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="text-xs text-text-muted">
                {formatTokenCount(session.tokenCount)} tok
              </span>
              {session.provider && (
                <span
                  className={cn(
                    'text-[10px] px-1.5 py-0.5 rounded',
                    session.provider.includes('gemini')
                      ? 'bg-gain/20 text-gain'
                      : 'bg-accent/20 text-accent',
                  )}
                >
                  {session.provider}
                </span>
              )}
              {onSelectSession && (
                <ChevronRight className="h-4 w-4 text-text-muted group-hover:text-text transition-colors" />
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={cn(
                'w-1.5 h-1.5 rounded-full',
                session.status === 'completed'
                  ? 'bg-gain'
                  : session.status === 'running'
                    ? 'bg-accent animate-pulse'
                    : session.status === 'error'
                      ? 'bg-loss'
                      : 'bg-neutral',
              )}
            />
            <span className="text-[10px] text-text-muted">
              {session.status}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

// Dev Companion Sessions List (for Agent Hub session history)
interface DevCompanionSessionsListProps {
  serverUrl?: string
  onSelectSession?: (session: DevCompanionSession) => void
  maxHeight?: string
}

// Get default server URL
// Use nginx proxy path /dev-companion/ for SSL termination
const getDefaultServerUrl = () => {
  if (typeof window === 'undefined') return 'http://localhost:9999'
  return `${window.location.origin}/dev-companion`
}

export function DevCompanionSessionsList({
  serverUrl,
  onSelectSession,
  maxHeight = '300px',
}: DevCompanionSessionsListProps) {
  // Use provided serverUrl or derive from current protocol
  const effectiveServerUrl = serverUrl || getDefaultServerUrl()
  const [sessions, setSessions] = useState<DevCompanionSession[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSessions = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const res = await fetch(`${effectiveServerUrl}/sessions?limit=20`)
        if (!res.ok) throw new Error('Failed to fetch sessions')
        const data = await res.json()
        setSessions(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sessions')
      } finally {
        setIsLoading(false)
      }
    }

    fetchSessions()
    // Refresh every 30 seconds
    const interval = setInterval(fetchSessions, 30 * 1000)
    return () => clearInterval(interval)
  }, [effectiveServerUrl])

  if (isLoading) {
    return (
      <div className="p-4 text-center text-text-muted text-sm">
        Loading sessions...
      </div>
    )
  }

  if (error) {
    return <div className="p-4 text-center text-loss text-sm">{error}</div>
  }

  if (sessions.length === 0) {
    return (
      <div className="p-4 text-center text-text-muted text-sm">
        No sessions yet
      </div>
    )
  }

  return (
    <div className="overflow-y-auto" style={{ maxHeight }}>
      {sessions.map((session) => (
        <div
          key={session.id}
          className={cn(
            'p-3 border-b border-border hover:bg-surface/50 cursor-pointer transition-colors',
            onSelectSession && 'group',
          )}
          onClick={() => onSelectSession?.(session)}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              {/* Session ID + Provider Badge */}
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-sm text-text">
                  {session.id.slice(0, 8)}
                </span>
                <ProviderBadge provider={session.originalProvider} size="xs" />
                {session.isActive && (
                  <span className="w-1.5 h-1.5 rounded-full bg-gain animate-pulse" />
                )}
              </div>
              {/* Description or "No messages yet" */}
              <div className="text-xs text-text-muted truncate">
                {session.description ||
                  (session.messageCount
                    ? 'No description'
                    : '(No messages yet)')}
              </div>
              {/* Participants row */}
              {session.participants && session.participants.length > 0 && (
                <div className="flex items-center gap-1 mt-1">
                  <span className="text-[10px] text-text-muted">
                    Participants:
                  </span>
                  {session.participants.map((p) => (
                    <ProviderBadge key={p} provider={p} size="xs" />
                  ))}
                </div>
              )}
            </div>
            <div className="flex flex-col items-end gap-1 text-right">
              {/* Message count */}
              {session.messageCount != null && session.messageCount > 0 && (
                <span className="text-xs text-text-muted">
                  {session.messageCount} msgs
                </span>
              )}
              {/* Relative time */}
              <span className="text-[10px] text-text-muted">
                {formatRelativeTime(session.updatedAt)}
              </span>
              {/* Created date */}
              <span className="text-[10px] text-text-muted">
                {new Date(session.createdAt).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  hour: 'numeric',
                  minute: '2-digit',
                })}
              </span>
              {onSelectSession && (
                <ChevronRight className="h-4 w-4 text-text-muted group-hover:text-text transition-colors" />
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
