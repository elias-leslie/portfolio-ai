import { Badge } from '@/components/ui/badge'
import type { Thesis } from '@/lib/api/thesis'

export function ClaudeValidationSection({
  validation,
}: {
  validation: NonNullable<Thesis['claudeValidation']>
}) {
  return (
    <div className="border-t border-border pt-3 space-y-2">
      <div className="flex items-center justify-between">
        <h5 className="text-xs font-semibold text-text">AI Validation</h5>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={
              validation.approved
                ? 'bg-status-success/10 text-status-success border-status-success/20'
                : 'bg-status-error/10 text-status-error border-status-error/20'
            }
          >
            {validation.approved ? 'Approved' : 'Not Approved'}
          </Badge>
          <span className="text-xs text-text-muted">
            {(validation.confidence * 100).toFixed(0)}% confidence
          </span>
        </div>
      </div>
      <p className="text-sm text-text-muted">{validation.reviewSummary}</p>
      {validation.issues.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-text">Issues:</p>
          <ul className="list-disc list-inside space-y-0.5">
            {validation.issues.map((issue, idx) => (
              <li key={idx} className="text-xs text-text-muted">
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
