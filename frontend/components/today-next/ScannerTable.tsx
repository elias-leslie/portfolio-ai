import Link from 'next/link'
import { SectionCard } from '@/components/shared/SectionCard'
import type { ScannerCandidate } from '@/lib/api/today-next'

function formatPercent(value?: number | null) {
  return typeof value === 'number' ? `${value.toFixed(0)}%` : '—'
}

function formatMoney(value?: number | null) {
  return typeof value === 'number' ? `$${value.toFixed(2)}` : '—'
}

export function ScannerTable({
  candidates,
}: {
  candidates: ScannerCandidate[]
}) {
  return (
    <SectionCard
      variant="surface"
      title="Scanner"
      description="Watchlist setups ranked by signal strength and current score."
      padding="none"
      contentClassName="overflow-x-auto"
    >
      <table className="min-w-full divide-y divide-border-subtle text-sm">
        <thead className="bg-bg/40 text-[10px] uppercase tracking-[0.18em] text-text-muted">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Symbol</th>
            <th className="px-4 py-3 text-left font-medium">Signal</th>
            <th className="px-4 py-3 text-left font-medium">Setup</th>
            <th className="px-4 py-3 text-right font-medium">Score</th>
            <th className="px-4 py-3 text-right font-medium">Entry</th>
            <th className="px-4 py-3 text-right font-medium">Stop</th>
            <th className="px-4 py-3 text-right font-medium">Target</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {candidates.map((candidate) => (
            <tr key={candidate.symbol} className="hover:bg-surface/60">
              <td className="px-4 py-3 font-mono text-sm font-semibold text-primary">
                <Link href={`/symbols/${candidate.symbol}`}>
                  {candidate.symbol}
                </Link>
              </td>
              <td className="px-4 py-3">
                <div className="font-medium text-text">
                  {candidate.signalType ?? '—'}
                </div>
                <div className="text-xs text-text-muted">
                  {formatPercent(candidate.signalStrength)} strength
                </div>
              </td>
              <td className="max-w-md px-4 py-3">
                <div className="truncate text-text">
                  {candidate.headline ?? 'No headline yet'}
                </div>
                <div className="text-xs text-text-muted">
                  {[candidate.style, candidate.riskLevel]
                    .filter(Boolean)
                    .join(' · ') || '—'}
                </div>
              </td>
              <td className="px-4 py-3 text-right font-mono text-text">
                {typeof candidate.score === 'number'
                  ? candidate.score.toFixed(1)
                  : '—'}
              </td>
              <td className="px-4 py-3 text-right font-mono text-text-muted">
                {formatMoney(candidate.entryPrice)}
              </td>
              <td className="px-4 py-3 text-right font-mono text-text-muted">
                {formatMoney(candidate.stopLoss)}
              </td>
              <td className="px-4 py-3 text-right font-mono text-text-muted">
                {formatMoney(candidate.profitTarget)}
              </td>
            </tr>
          ))}
          {candidates.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-4 py-8 text-center text-text-muted">
                No scanner candidates.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </SectionCard>
  )
}
