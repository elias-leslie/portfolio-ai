import type { PermissionRequest } from './types'

interface PermissionModalProps {
  permission: PermissionRequest
  onRespond: (allowed: boolean) => void
}

export function PermissionModal({
  permission,
  onRespond,
}: PermissionModalProps) {
  return (
    <div className="border-t border-warning bg-warning/30 p-4">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 text-2xl">&#9888;</div>
        <div className="flex-1">
          <h4 className="font-semibold text-warning mb-2">
            Permission Required
          </h4>
          <p className="text-sm text-warning mb-2">
            Claude wants to use:{' '}
            <span className="font-mono font-bold">{permission.toolName}</span>
          </p>
          {permission.toolInput &&
            Object.keys(permission.toolInput).length > 0 && (
              <div className="bg-surface/50 rounded p-2 mb-3 max-h-32 overflow-y-auto">
                <pre className="text-xs text-text whitespace-pre-wrap font-mono">
                  {JSON.stringify(permission.toolInput, null, 2)}
                </pre>
              </div>
            )}
          <div className="flex gap-2">
            <button
              onClick={() => onRespond(true)}
              className="px-4 py-2 bg-gain text-text-inverted rounded hover:bg-gain-strong font-medium"
            >
              Allow
            </button>
            <button
              onClick={() => onRespond(false)}
              className="px-4 py-2 bg-loss text-text-inverted rounded hover:bg-loss-strong font-medium"
            >
              Deny
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
