import type { SymbolWorkflowEvent } from '@/lib/api/symbols'

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

export function WorkflowEvidenceSnapshot({
  event,
}: {
  event: SymbolWorkflowEvent
}) {
  const evidence = record(event.metadata?.evidenceSnapshot)
  if (!evidence)
    return (
      <p className="mt-2 text-xs text-text-muted">
        No source snapshot was retained with this older entry.
      </p>
    )
  const decision = record(evidence.decision)
  const quote = record(evidence.quote)
  const portfolio = record(evidence.portfolio)
  const reasons = Array.isArray(decision?.reasoning)
    ? decision.reasoning.filter(
        (value): value is string => typeof value === 'string',
      )
    : []
  const gaps = Array.isArray(decision?.missingEvidence)
    ? decision.missingEvidence.filter(
        (value): value is string => typeof value === 'string',
      )
    : []
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer font-medium">
        Evidence saved with this decision
      </summary>
      <div className="mt-2 space-y-2 text-text-muted">
        <p>
          Captured at save time:{' '}
          {typeof evidence.capturedAt === 'string'
            ? new Date(evidence.capturedAt).toLocaleString()
            : event.createdAt}
          .
        </p>
        <p>
          {typeof decision?.sourceLabel === 'string'
            ? decision.sourceLabel
            : 'Decision source unavailable'}{' '}
          ·{' '}
          {typeof decision?.headline === 'string'
            ? decision.headline
            : 'No decision'}{' '}
          ·{' '}
          {portfolio?.held === true
            ? 'Held'
            : portfolio?.held === false
              ? 'Not held'
              : 'Exposure unknown'}
        </p>
        <p>
          Price{' '}
          {typeof quote?.price === 'number'
            ? `$${quote.price.toFixed(2)}`
            : 'unavailable'}{' '}
          ·{' '}
          {typeof quote?.source === 'string'
            ? quote.source
            : 'source unavailable'}{' '}
          ·{' '}
          {typeof quote?.quoteTime === 'string'
            ? `Quoted ${new Date(quote.quoteTime).toLocaleString()}`
            : typeof quote?.cachedAt === 'string'
              ? `Cached ${new Date(quote.cachedAt).toLocaleString()}; quote time unavailable`
              : 'source age unknown'}
        </p>
        {reasons.length > 0 ? (
          <ul className="list-disc pl-5">
            {reasons.map((value) => (
              <li key={value}>{value}</li>
            ))}
          </ul>
        ) : null}
        {gaps.length > 0 ? <p>Evidence gaps: {gaps.join(' ')}</p> : null}
      </div>
    </details>
  )
}
