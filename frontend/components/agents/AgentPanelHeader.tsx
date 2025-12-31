'use client';

import { MessageSquare, Settings, Activity, Camera } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ProviderBadge } from './ProviderBadge';
import type { AgentProvider } from './AgentSelector';

interface PageContext {
  path: string;
  data?: Record<string, unknown>;
}

interface SessionInfo {
  originalProvider?: AgentProvider | 'both';
}

interface AgentPanelHeaderProps {
  isConnected: boolean;
  pageContext?: PageContext;
  currentSessionId: string | null;
  currentSession: SessionInfo | null;
  agentProvider: AgentProvider;
  showSessions: boolean;
  onShowEvidenceCapture: () => void;
  onShowStatus: () => void;
  onShowSettings: () => void;
  onToggleSessions: () => void;
}

export function AgentPanelHeader({
  isConnected,
  pageContext,
  currentSessionId,
  currentSession,
  agentProvider,
  showSessions,
  onShowEvidenceCapture,
  onShowStatus,
  onShowSettings,
  onToggleSessions,
}: AgentPanelHeaderProps) {
  return (
    <div className="p-4 border-b border-border space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-text">Agent Hub</h2>
          <span className={cn(
            "w-2 h-2 rounded-full",
            isConnected ? "bg-gain" : "bg-loss"
          )} />
        </div>
        {/* Header Icons: Evidence, Status, Settings */}
        <div className="flex items-center gap-1">
          {/* Evidence Capture */}
          <Button
            variant="ghost"
            size="sm"
            onClick={onShowEvidenceCapture}
            disabled={!pageContext?.path}
            className="h-8 w-8 p-0 text-text-muted hover:text-text disabled:opacity-50"
            title={pageContext?.path ? "Capture page evidence" : "No page context"}
          >
            <Camera className="h-4 w-4" />
          </Button>
          {/* Status */}
          <Button
            variant="ghost"
            size="sm"
            onClick={onShowStatus}
            className="h-8 w-8 p-0 text-text-muted hover:text-text"
            title="Status"
          >
            <Activity className="h-4 w-4" />
          </Button>
          {/* Settings */}
          <Button
            variant="ghost"
            size="sm"
            onClick={onShowSettings}
            className="h-8 w-8 p-0 text-text-muted hover:text-text"
            title="Settings"
          >
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {/* Page context indicator */}
      <div className="flex items-center gap-2 text-xs">
        <span className="text-text-muted">Tracking:</span>
        <span className={cn(
          "font-mono px-1.5 py-0.5 rounded",
          pageContext?.path
            ? "bg-primary-surface text-primary"
            : "bg-surface-muted text-text-muted"
        )}>
          {pageContext?.path || "No page"}
        </span>
      </div>
      {/* Sessions button (left) + Session ID + Provider info (right) */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Sessions Button - left side */}
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleSessions}
            className={cn(
              "h-7 px-2 text-text-muted hover:text-text text-xs",
              showSessions && "bg-surface-muted text-text"
            )}
            title="Sessions"
          >
            <MessageSquare className="h-3.5 w-3.5 mr-1" />
            Sessions
          </Button>
          <span className="text-border">|</span>
          <span className="text-text-muted text-xs flex items-center gap-1">
            {currentSessionId ? `${currentSessionId.slice(0, 8)}...` : 'No session'}
            {/* Show original provider badge if session has one */}
            {currentSession?.originalProvider && (
              <ProviderBadge provider={currentSession.originalProvider} size="xs" />
            )}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Show "Started with: X" if current agent differs from original */}
          {currentSession?.originalProvider &&
           currentSession.originalProvider !== 'both' &&
           currentSession.originalProvider !== agentProvider && (
            <span className="text-xs text-text-muted flex items-center gap-1">
              Started with: <ProviderBadge provider={currentSession.originalProvider} size="xs" />
            </span>
          )}
          {isConnected && (
            <span className={cn(
              "text-xs px-1.5 py-0.5 rounded font-medium",
              agentProvider === 'both'
                ? "bg-accent/30 text-accent border border-accent"
                : agentProvider === 'gemini'
                  ? "bg-gain/30 text-gain border border-gain"
                  : "bg-primary/30 text-primary border border-primary"
            )}>
              {agentProvider === 'both'
                ? 'Claude + Gemini'
                : agentProvider === 'gemini' ? 'Gemini' : 'Claude'}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
