'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { MessageSquare, Users, RefreshCw, Bot, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface SessionInfo {
  id: string;
  agent_type: string;
  run_type: string;
  session_type: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  provider: string | null;
  model: string | null;
  token_count: number;
  parent_run_id: string | null;
  summary: string | null;
}

function formatTokenCount(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`;
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}K`;
  }
  return tokens.toString();
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hr ago`;
  if (diffDays === 1) return 'yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString();
}

function SessionTypeBadge({ type }: { type: string }) {
  const config = {
    user_single_agent: { icon: MessageSquare, label: 'User Chat', color: 'text-blue-400 bg-blue-900/30' },
    user_multi_agent: { icon: Users, label: 'Roundtable', color: 'text-purple-400 bg-purple-900/30' },
    agent_agent_validation: { icon: RefreshCw, label: 'Validation', color: 'text-amber-400 bg-amber-900/30' },
    agent_autonomous: { icon: Bot, label: 'Automated', color: 'text-green-400 bg-green-900/30' },
  }[type] || { icon: Bot, label: type, color: 'text-gray-400 bg-gray-700' };

  const Icon = config.icon;

  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', config.color)}>
      <Icon className="h-3 w-3" />
      {config.label}
    </span>
  );
}

interface SessionsListProps {
  serverUrl?: string;
  onSelectSession?: (session: SessionInfo) => void;
  maxHeight?: string;
}

export function SessionsList({
  serverUrl = 'http://localhost:8000',
  onSelectSession,
  maxHeight = '300px'
}: SessionsListProps) {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSessions = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch(`${serverUrl}/api/agents/sessions?limit=20`);
        if (!res.ok) throw new Error('Failed to fetch sessions');
        const data = await res.json();
        setSessions(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sessions');
      } finally {
        setIsLoading(false);
      }
    };

    fetchSessions();
    // Refresh every minute
    const interval = setInterval(fetchSessions, 60 * 1000);
    return () => clearInterval(interval);
  }, [serverUrl]);

  if (isLoading) {
    return (
      <div className="p-4 text-center text-gray-500 text-sm">
        Loading sessions...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center text-red-400 text-sm">
        {error}
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="p-4 text-center text-gray-500 text-sm">
        No agent sessions yet
      </div>
    );
  }

  return (
    <div className="overflow-y-auto" style={{ maxHeight }}>
      {sessions.map((session) => (
        <div
          key={session.id}
          className={cn(
            "p-3 border-b border-gray-700 hover:bg-gray-800/50 cursor-pointer transition-colors",
            onSelectSession && "group"
          )}
          onClick={() => onSelectSession?.(session)}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <SessionTypeBadge type={session.session_type} />
                <span className="text-xs text-gray-500">
                  {formatRelativeTime(session.started_at)}
                </span>
              </div>
              <div className="text-sm text-gray-300 font-medium truncate">
                {session.agent_type}
              </div>
              {session.summary && (
                <div className="text-xs text-gray-500 truncate mt-0.5">
                  {session.summary}
                </div>
              )}
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="text-xs text-gray-400">
                {formatTokenCount(session.token_count)} tok
              </span>
              {session.provider && (
                <span className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded",
                  session.provider.includes('gemini')
                    ? "bg-green-900/30 text-green-400"
                    : "bg-blue-900/30 text-blue-400"
                )}>
                  {session.provider}
                </span>
              )}
              {onSelectSession && (
                <ChevronRight className="h-4 w-4 text-gray-600 group-hover:text-gray-400 transition-colors" />
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={cn(
              "w-1.5 h-1.5 rounded-full",
              session.status === 'completed' ? "bg-green-500" :
              session.status === 'running' ? "bg-blue-500 animate-pulse" :
              session.status === 'error' ? "bg-red-500" : "bg-gray-500"
            )} />
            <span className="text-[10px] text-gray-600">{session.status}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
