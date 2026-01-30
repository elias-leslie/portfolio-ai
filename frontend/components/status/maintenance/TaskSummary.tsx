interface TaskSummaryProps {
  summary: Record<string, unknown> | null
}

export function TaskSummary({ summary }: TaskSummaryProps) {
  if (!summary) return null

  // Cleanup News summary
  if ('deleted' in summary) {
    return (
      <div className="text-sm space-y-1">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Articles deleted:</span>
          <span className="font-mono">{String(summary.deleted)}</span>
        </div>
        {typeof summary.cutoffDate === 'string' && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">Cutoff date:</span>
            <span className="font-mono text-xs">
              {new Date(String(summary.cutoffDate)).toLocaleDateString()}
            </span>
          </div>
        )}
      </div>
    )
  }

  // Vacuum Database summary
  if ('tables_processed' in summary) {
    return (
      <div className="text-sm space-y-1">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Tables processed:</span>
          <span className="font-mono">{String(summary.tablesProcessed)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Space reclaimed:</span>
          <span className="font-mono">
            {String(summary.totalReclaimedMb)} MB
          </span>
        </div>
      </div>
    )
  }

  // Validate Integrity summary
  if ('checks_run' in summary) {
    return (
      <div className="text-sm space-y-1">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Checks run:</span>
          <span className="font-mono">{String(summary.checksRun)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Errors:</span>
          <span className="font-mono text-loss">
            {String(summary.totalErrors ?? 0)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Warnings:</span>
          <span className="font-mono text-warning">
            {String(summary.totalWarnings ?? 0)}
          </span>
        </div>
      </div>
    )
  }

  // Fallback: show JSON
  return (
    <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-32">
      {JSON.stringify(summary, null, 2)}
    </pre>
  )
}
