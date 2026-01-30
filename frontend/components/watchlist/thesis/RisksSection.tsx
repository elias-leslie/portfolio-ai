import type { Risk } from '@/lib/api/thesis'
import { SeverityBadge } from './SeverityBadge'

export function RisksSection({ risks }: { risks: Risk[] }) {
  return (
    <div className="border-t border-border pt-3 space-y-2">
      <h5 className="text-xs font-semibold text-text">Risks</h5>
      <div className="space-y-2">
        {risks.map((risk, idx) => (
          <div key={idx} className="space-y-1">
            <div className="flex items-start gap-2">
              <SeverityBadge severity={risk.severity} />
              <div className="flex-1">
                <p className="text-sm text-text">{risk.risk}</p>
                {risk.mitigation && (
                  <p className="text-xs text-text-muted mt-1">
                    <span className="font-medium">Mitigation:</span>{' '}
                    {risk.mitigation}
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
