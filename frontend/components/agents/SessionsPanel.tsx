'use client'

import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn, formatRelativeTime } from '@/lib/utils'
import type { Session } from './hooks'
import { ProviderBadge } from './ProviderBadge'

interface SessionsPanelProps {
  sessions: Session[]
  currentSessionId: string | null
  isLoadingSessions: boolean
  showTokenSummary: boolean
  onSessionSelect: (sessionId: string) => void
  onCreateSession: () => void
  onDeleteSession: (sessionId: string) => void
  onToggleTokenSummary: () => void
}

export function SessionsPanel({
  sessions,
  currentSessionId,
  isLoadingSessions,
  showTokenSummary,
  onSessionSelect,
  onCreateSession,
  onDeleteSession,
  onToggleTokenSummary,
}: SessionsPanelProps) {
  return (
    <div className="border-b border-border bg-surface/30">
      <div className="p-2 flex items-center justify-between border-b border-border">
        <span className="text-xs text-text-muted font-medium">Sessions</span>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleTokenSummary}
            className="h-6 px-2 text-xs text-text-muted hover:text-text"
          >
            {showTokenSummary ? 'Hide Tokens' : 'Show Tokens'}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={onCreateSession}
            className="h-6 px-2 text-xs text-gain hover:text-gain-strong"
          >
            <Plus className="h-3 w-3 mr-1" /> New
          </Button>
        </div>
      </div>
      {isLoadingSessions ? (
        <div className="p-4 text-center text-text-muted text-sm">
          Loading...
        </div>
      ) : sessions.length === 0 ? (
        <div className="p-4 text-center text-text-muted text-sm">
          No sessions yet
        </div>
      ) : (
        <div className="overflow-y-auto" style={{ maxHeight: '250px' }}>
          {sessions.map((session) => (
            <div
              key={session.id}
              className={cn(
                'p-3 border-b border-border hover:bg-surface/50 cursor-pointer transition-colors',
                currentSessionId === session.id && 'bg-surface-muted',
              )}
              onClick={() => onSessionSelect(session.id)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  {/* Session ID + Provider Badge */}
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={cn(
                        'w-2 h-2 rounded-full',
                        session.isActive ? 'bg-gain' : 'bg-border',
                      )}
                    />
                    <span className="font-mono text-sm text-text">
                      {session.id.slice(0, 8)}
                    </span>
                    <ProviderBadge
                      provider={session.originalProvider}
                      size="xs"
                    />
                  </div>
                  {/* Description or placeholder */}
                  <div className="text-xs text-text-muted truncate">
                    {session.description ||
                      (session.messageCount
                        ? 'No description'
                        : '(No messages yet)')}
                  </div>
                  {/* Participants row */}
                  {session.participants && session.participants.length > 0 && (
                    <div className="flex items-center gap-1 mt-1">
                      <span className="text-[10px] text-border">
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
                  {/* Delete button */}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteSession(session.id)
                    }}
                    className="h-6 w-6 p-0 text-text-muted hover:text-loss"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
