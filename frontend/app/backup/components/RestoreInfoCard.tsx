import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function RestoreInfoCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Restore Information</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-text-muted">
          To restore from a backup, use the command line:
        </p>

        <div className="rounded-md bg-surface-muted p-3 font-mono text-xs space-y-2">
          <div className="text-text-muted"># List available backups</div>
          <div>bash ~/portfolio-ai/scripts/restore.sh --list</div>

          <div className="text-text-muted mt-3"># Restore latest backup</div>
          <div>bash ~/portfolio-ai/scripts/restore.sh --latest</div>

          <div className="text-text-muted mt-3"># Restore specific backup</div>
          <div>
            bash ~/portfolio-ai/scripts/restore.sh
            portfolio-ai-YYYYMMDD-HHMMSS.tar.gz
          </div>

          <div className="text-text-muted mt-3"># Database only</div>
          <div>bash ~/portfolio-ai/scripts/restore.sh --db-only --latest</div>
        </div>

        <div className="rounded-md border border-warning bg-warning/10 p-3 text-sm text-warning">
          <strong>Warning:</strong> Restore operations will overwrite existing
          data. Make sure you have a current backup before restoring.
        </div>
      </CardContent>
    </Card>
  )
}
