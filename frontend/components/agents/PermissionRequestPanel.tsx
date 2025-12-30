'use client';

import { Button } from '@/components/ui/button';
import type { PermissionRequest } from './wsHandlers';

interface PermissionRequestPanelProps {
  permission: PermissionRequest;
  onRespond: (allowed: boolean) => void;
}

/**
 * Panel shown when an agent tool requires explicit user permission.
 * Displays the tool name, input parameters, and allow/deny buttons.
 */
export function PermissionRequestPanel({ permission, onRespond }: PermissionRequestPanelProps) {
  return (
    <div className="border-t border-warning bg-warning/30 p-4">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 text-xl">⚠</div>
        <div className="flex-1">
          <h4 className="font-semibold text-warning mb-2">Permission Required</h4>
          <p className="text-sm text-warning mb-2">
            Claude wants to use: <span className="font-mono font-bold">{permission.toolName}</span>
          </p>
          {permission.toolInput && Object.keys(permission.toolInput).length > 0 && (
            <div className="bg-surface/50 rounded p-2 mb-3 max-h-24 overflow-y-auto">
              <pre className="text-xs text-text whitespace-pre-wrap font-mono">
                {JSON.stringify(permission.toolInput, null, 2)}
              </pre>
            </div>
          )}
          <div className="flex gap-2">
            <Button onClick={() => onRespond(true)} size="sm" className="bg-gain hover:bg-gain-strong">
              Allow
            </Button>
            <Button onClick={() => onRespond(false)} size="sm" variant="destructive">
              Deny
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
