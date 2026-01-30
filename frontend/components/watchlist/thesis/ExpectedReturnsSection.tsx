import type { Thesis } from '@/lib/api/thesis'

export function ExpectedReturnsSection({ thesis }: { thesis: Thesis }) {
  return (
    <div className="border-t border-border pt-3">
      <h5 className="text-xs font-semibold text-text mb-2">Expected Returns</h5>
      <div className="grid grid-cols-2 gap-3">
        {thesis.expectedReturnPct !== null && (
          <div className="bg-surface-muted/50 rounded px-2 py-1.5">
            <p className="text-xs text-text-muted">Return</p>
            <p className="text-sm font-semibold text-text">
              {thesis.expectedReturnPct > 0 ? '+' : ''}
              {thesis.expectedReturnPct.toFixed(1)}%
            </p>
          </div>
        )}
        {thesis.expectedTimeframeDays !== null && (
          <div className="bg-surface-muted/50 rounded px-2 py-1.5">
            <p className="text-xs text-text-muted">Timeframe</p>
            <p className="text-sm font-semibold text-text">
              {thesis.expectedTimeframeDays} days
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
