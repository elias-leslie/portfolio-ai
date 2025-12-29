'use client';

import { Camera, Eye } from 'lucide-react';
import { cn } from '@/lib/utils';
import { type ChatMessage } from './wsHandlers';

interface EvidenceMessageBubbleProps {
  message: ChatMessage;
  onViewEvidence: () => void;
}

export function EvidenceMessageBubble({
  message,
  onViewEvidence
}: EvidenceMessageBubbleProps) {
  const evidence = message.evidence!;
  const hasErrors = evidence.consoleErrors > 0 || evidence.networkFailures > 0;

  return (
    <div className="flex justify-start">
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors",
          "bg-surface hover:bg-surface-muted border",
          hasErrors ? "border-loss/50" : "border-primary/50"
        )}
        onClick={onViewEvidence}
      >
        <div className="flex items-center gap-2 mb-1">
          <Camera className="h-4 w-4 text-primary" />
          <span className="font-medium">Evidence Captured</span>
          <span className="text-xs text-text-muted">v{evidence.version}</span>
        </div>
        <div className="text-xs text-text-muted mb-2">
          {evidence.featureId} / {evidence.criterionId}
        </div>
        <div className="flex items-center gap-3 text-xs">
          {evidence.consoleErrors > 0 && (
            <span className="text-loss">
              {evidence.consoleErrors} console error{evidence.consoleErrors !== 1 ? 's' : ''}
            </span>
          )}
          {evidence.networkFailures > 0 && (
            <span className="text-loss">
              {evidence.networkFailures} network failure{evidence.networkFailures !== 1 ? 's' : ''}
            </span>
          )}
          {!hasErrors && (
            <span className="text-gain">No issues detected</span>
          )}
        </div>
        <div className="flex items-center gap-1 mt-2 text-xs text-primary">
          <Eye className="h-3 w-3" />
          Click to view evidence
        </div>
        <div className="text-xs opacity-50 mt-1">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
