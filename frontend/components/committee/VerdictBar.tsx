'use client'

import { Button } from '@/components/ui/button'
import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

const ACTION_TONE: Record<string, string> = {
  buy: 'text-gain-strong',
  add: 'text-gain',
  sell: 'text-loss-strong',
  trim: 'text-loss',
  hold: 'text-warning-strong',
}

const SIGNER_GROUPS: Array<{ label: string; slugs: string[] }> = [
  { label: 'FUND', slugs: ['fundamentals-v1'] },
  { label: 'NEWS', slugs: ['news-grounded-v1'] },
  { label: 'SENT', slugs: ['sentiment-grounded-v1'] },
  { label: 'TECH', slugs: ['technical-v1'] },
  { label: 'BULL', slugs: ['bull-researcher-v1'] },
  { label: 'BEAR', slugs: ['bear-researcher-v1'] },
  { label: 'TRAD', slugs: ['trader-v1'] },
  {
    label: 'RISK',
    slugs: ['risk-aggressive-v1', 'risk-neutral-v1', 'risk-conservative-v1'],
  },
  { label: 'PM', slugs: ['portfolio-mgr-v1'] },
]

function signerState(
  group: (typeof SIGNER_GROUPS)[number],
  state: CommitteeUiState,
): 'yes' | 'no' | 'pending' {
  const signers = state.decision?.signers ?? []
  if (signers.length === 0) return 'pending'
  const any = group.slugs.some((slug) => signers.includes(slug))
  if (any) return 'yes'
  // If the decision is issued and none of this group is in signers, treat as 'no'.
  if (state.decision) return 'no'
  return 'pending'
}

export function VerdictBar({
  state,
  onApprove,
  onAbort,
  onRetro,
  approving,
}: {
  state: CommitteeUiState
  onApprove: () => void
  onAbort: () => void
  onRetro: () => void
  approving: boolean
}) {
  const decision = state.decision
  const proposal = state.proposal
  const action = decision?.action ?? proposal?.action ?? null
  const tone = action ? (ACTION_TONE[action] ?? 'text-text') : 'text-text-muted'
  const isProvisional = !decision && proposal
  const qtyPctText = decision
    ? `${(decision.qty_pct * 100).toFixed(1)}%`
    : proposal
      ? `${(proposal.qty_pct * 100).toFixed(1)}%`
      : '—'
  const confText = decision ? decision.confidence.toFixed(2) : '—'
  const horizonText = decision?.horizon ?? proposal?.horizon ?? '—'
  const entryPrice = decision?.qty
    ? (proposal?.entry_price ?? null)
    : (proposal?.entry_price ?? null)

  return (
    <div
      className={cn(
        'grid grid-cols-1 items-center gap-4 rounded-2xl border bg-gradient-to-r from-surface to-bg px-4 py-3 lg:grid-cols-[auto_auto_1fr_auto]',
        decision?.action === 'hold'
          ? 'border-warning/40'
          : decision
            ? 'border-gain/40'
            : 'border-border',
      )}
    >
      <div>
        <p className="text-[9px] font-semibold uppercase tracking-[0.22em] text-text-muted/70">
          {isProvisional ? 'Provisional verdict' : 'Verdict'}
        </p>
        <p
          className={cn(
            'mt-0.5 font-display text-2xl italic leading-tight tracking-tight',
            tone,
          )}
        >
          {action
            ? action === 'hold'
              ? 'Hold'
              : `${action[0].toUpperCase()}${action.slice(1)} ${qtyPctText}`
            : '—'}
        </p>
      </div>

      <div className="text-[12px] leading-relaxed text-text-muted">
        {decision ? (
          <>
            <span className="font-mono text-text">{qtyPctText}</span> portfolio
            {decision.qty && entryPrice ? (
              <>
                {' '}
                ·{' '}
                <span className="font-mono text-text">
                  {decision.qty.toFixed(0)}
                </span>{' '}
                sh @{' '}
                <span className="font-mono text-text">
                  ${entryPrice.toFixed(2)}
                </span>
              </>
            ) : null}
            <br />
            conf <span className="font-mono text-text">{confText}</span> ·
            horizon <span className="font-mono text-text">{horizonText}</span>
          </>
        ) : (
          <span className="text-text-muted/60">
            PM has not issued a decision yet.
          </span>
        )}
      </div>

      <div>
        <p className="mb-1 text-[9px] font-semibold uppercase tracking-[0.22em] text-text-muted/70">
          Committee signatures
        </p>
        <div className="flex flex-wrap gap-1">
          {SIGNER_GROUPS.map((group) => {
            const value = signerState(group, state)
            return (
              <span
                key={group.label}
                className={cn(
                  'rounded-md border bg-bg px-1.5 py-0.5 font-mono text-[9px]',
                  value === 'yes' && 'border-gain/50 text-gain-strong',
                  value === 'no' && 'border-loss/50 text-loss-strong',
                  value === 'pending' &&
                    'border-border-subtle text-text-muted/60',
                )}
              >
                {group.label}{' '}
                {value === 'yes' ? '✓' : value === 'no' ? '✗' : '?'}
              </span>
            )
          })}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {state.status === 'complete' && decision ? (
          <>
            <Button variant="outline" size="sm" onClick={onAbort}>
              Discard
            </Button>
            <Button
              size="sm"
              onClick={onApprove}
              disabled={approving || decision.action === 'hold'}
            >
              {approving
                ? 'Executing…'
                : decision.action === 'hold'
                  ? 'Hold (no trade)'
                  : 'Approve & execute'}
            </Button>
          </>
        ) : null}
        {state.status === 'approved' ? (
          <Button variant="outline" size="sm" onClick={onRetro}>
            Start Retro
          </Button>
        ) : null}
      </div>

      {decision?.rationale_md ? (
        <div className="col-span-full text-[12px] leading-relaxed text-text">
          <p className="text-[9px] font-semibold uppercase tracking-[0.22em] text-text-muted/70">
            PM rationale
          </p>
          <p className="mt-1 whitespace-pre-wrap text-text-muted">
            {decision.rationale_md}
          </p>
        </div>
      ) : null}
      {decision?.rebuttal_md ? (
        <div className="col-span-full rounded-xl border border-warning/40 bg-warning/10 p-3 text-[12px] leading-relaxed text-text">
          <p className="text-[9px] font-semibold uppercase tracking-[0.22em] text-warning-strong">
            Rebuttal to user input
          </p>
          <p className="mt-1 whitespace-pre-wrap">{decision.rebuttal_md}</p>
        </div>
      ) : null}
    </div>
  )
}
