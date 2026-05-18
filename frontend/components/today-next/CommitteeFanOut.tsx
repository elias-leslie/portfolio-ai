import Link from 'next/link'
import { SectionCard } from '@/components/shared/SectionCard'
import type { CommitteeCandidate } from '@/lib/api/today-next'

function formatPct(value?: number | null) {
  return typeof value === 'number' ? `${(value * 100).toFixed(0)}%` : '—'
}

function formatReturn(value?: number | null) {
  return typeof value === 'number' ? `${value.toFixed(1)}%` : '—'
}

export function CommitteeFanOut({
  candidates,
}: {
  candidates: CommitteeCandidate[]
}) {
  return (
    <SectionCard
      variant="surface"
      title="Committee fan-out"
      description="Thesis builder and cross-validation layer, joined to latest committee run when present."
      padding="md"
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {candidates.map((candidate) => (
          <div
            key={`${candidate.symbol}-${candidate.committeeRunId ?? 'thesis'}`}
            className="rounded-2xl border border-border-subtle bg-bg/40 p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <Link
                  href={`/symbols/${candidate.symbol}`}
                  className="font-mono text-lg font-semibold text-primary"
                >
                  {candidate.symbol}
                </Link>
                <div className="mt-1 text-xs uppercase tracking-[0.16em] text-text-muted">
                  {candidate.thesisStatus ?? 'thesis'}
                </div>
              </div>
              <div className="rounded-full border border-border-subtle px-2 py-1 text-xs text-text">
                {candidate.thesisAction ?? '—'}
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
                  Thesis return
                </div>
                <div className="mt-1 font-mono text-text">
                  {formatReturn(candidate.expectedReturnPct)}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
                  Cross-val
                </div>
                <div className="mt-1 font-mono text-text">
                  {formatPct(candidate.crossValidationScore)}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
                  Committee
                </div>
                <div className="mt-1 text-text">
                  {candidate.committeeAction ??
                    candidate.committeeStatus ??
                    'No run'}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
                  Confidence
                </div>
                <div className="mt-1 font-mono text-text">
                  {formatPct(candidate.committeeConfidence)}
                </div>
              </div>
            </div>
            {candidate.committeeRunId ? (
              <Link
                href={`/portfolio/committee/${candidate.committeeRunId}`}
                className="mt-4 inline-flex text-xs font-medium text-primary hover:underline"
              >
                Open committee run
              </Link>
            ) : null}
          </div>
        ))}
        {candidates.length === 0 ? (
          <div className="rounded-2xl border border-border-subtle bg-bg/40 p-6 text-sm text-text-muted">
            No thesis or committee candidates for current scanner set.
          </div>
        ) : null}
      </div>
    </SectionCard>
  )
}
