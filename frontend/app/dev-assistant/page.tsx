'use client';

import { useState, useEffect, useCallback } from 'react';
import ChatPanel from '@/components/dev-assistant/ChatPanel';
import { getServerUrl, getWsUrl } from '@/lib/server-url';

interface Session {
  id: string;
  workingDir: string;
  createdAt: string;
  updatedAt: string;
  isActive: boolean;
  metadata: Record<string, unknown>;
}

export default function DevAssistantPage() {
  const [serverUrl, setServerUrl] = useState<string | null>(null);
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Set URLs on client side
  useEffect(() => {
    const url = getServerUrl();
    if (url) {
      setServerUrl(url);
      setWsUrl(getWsUrl(url));
    }
  }, []);

  // Fetch sessions when URL is available
  const fetchSessions = useCallback(async () => {
    if (!serverUrl) return;

    try {
      const response = await fetch(`${serverUrl}/sessions`);
      if (!response.ok) throw new Error('Failed to fetch sessions');
      const data = await response.json();
      setSessions(data);

      // Auto-select most recent session or create new one
      if (data.length > 0) {
        setCurrentSessionId(data[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect to Dev Companion server');
    } finally {
      setIsLoading(false);
    }
  }, [serverUrl]);

  useEffect(() => {
    if (serverUrl) {
      fetchSessions();
    }
  }, [serverUrl, fetchSessions]);

  const createSession = async () => {
    if (!serverUrl) return;

    try {
      const response = await fetch(`${serverUrl}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workingDir: '/home/kasadis/portfolio-ai',
        }),
      });
      if (!response.ok) throw new Error('Failed to create session');
      const session = await response.json();
      setSessions(prev => [session, ...prev]);
      setCurrentSessionId(session.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session');
    }
  };

  const deleteSession = async (sessionId: string) => {
    if (!serverUrl) return;

    try {
      await fetch(`${serverUrl}/sessions/${sessionId}`, { method: 'DELETE' });
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        setCurrentSessionId(sessions.find(s => s.id !== sessionId)?.id || null);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  if (!serverUrl || isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg text-text">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4" />
          <p>Connecting to Dev Companion...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg text-text">
        <div className="text-center max-w-md">
          <div className="text-loss text-4xl mb-4">!</div>
          <h1 className="text-xl font-bold mb-2">Connection Error</h1>
          <p className="text-text-muted mb-4">{error}</p>
          <p className="text-sm text-text-muted mb-4">
            Make sure the Dev Companion server is running on port 9999.
          </p>
          <button
            onClick={() => {
              setError(null);
              setIsLoading(true);
              fetchSessions();
            }}
            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-bg">
      {/* Sidebar - Sessions */}
      <div className="w-64 border-r border-border flex flex-col">
        <div className="p-4 border-b border-border">
          <h1 className="text-lg font-bold text-text">Dev Assistant</h1>
          <p className="text-xs text-text-muted">Powered by Claude Code</p>
        </div>

        <div className="p-2">
          <button
            onClick={createSession}
            className="w-full px-3 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 text-sm"
          >
            + New Session
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {sessions.map(session => (
            <div
              key={session.id}
              className={`px-3 py-2 cursor-pointer border-l-2 ${
                currentSessionId === session.id
                  ? 'bg-surface border-primary'
                  : 'border-transparent hover:bg-surface/50'
              }`}
              onClick={() => setCurrentSessionId(session.id)}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-text font-mono">{session.id}</span>
                <div className="flex items-center gap-1">
                  {session.isActive && (
                    <span className="w-2 h-2 rounded-full bg-gain" title="Active" />
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSession(session.id);
                    }}
                    className="text-text-muted hover:text-loss text-xs"
                    title="Delete session"
                  >
                    x
                  </button>
                </div>
              </div>
              <div className="text-xs text-text-muted truncate" title={session.workingDir}>
                {session.workingDir.split('/').pop()}
              </div>
              <div className="text-xs text-text-muted">
                {new Date(session.updatedAt).toLocaleDateString()}
              </div>
            </div>
          ))}

          {sessions.length === 0 && (
            <div className="px-3 py-4 text-center text-text-muted text-sm">
              No sessions yet. Create one to start.
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {currentSessionId && wsUrl ? (
          <ChatPanel sessionId={currentSessionId} serverUrl={wsUrl} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-text-muted">
            <div className="text-center">
              <p className="mb-4">No session selected</p>
              <button
                onClick={createSession}
                className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90"
              >
                Create New Session
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
