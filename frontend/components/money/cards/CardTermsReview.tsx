'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { get, post } from '@/lib/api/client'

type TermProposal = {
  id: string
  productSlug: string
  proposedFields: Record<string, unknown>
  previousFields: Record<string, unknown>
  evidence: Record<
    string,
    { sourceUrl?: string; excerpt?: string; effectiveFrom?: string }
  >
  fingerprint: string
}

function safeSource(value: string | undefined) {
  if (!value) return undefined
  try {
    const url = new URL(value)
    const domains = [
      'chase.com',
      'americanexpress.com',
      'capitalone.com',
      'citi.com',
      'wellsfargo.com',
    ]
    return url.protocol === 'https:' &&
      domains.some(
        (domain) =>
          url.hostname === domain || url.hostname.endsWith(`.${domain}`),
      )
      ? url.href
      : undefined
  } catch {
    return undefined
  }
}

function termValue(value: unknown) {
  return typeof value === 'object'
    ? JSON.stringify(value)
    : String(value ?? 'Not recorded')
}

export function CardTermsReview() {
  const client = useQueryClient()
  const query = useQuery({
    queryKey: ['cards', 'terms-review'],
    queryFn: ({ signal }) =>
      get<TermProposal[]>('/api/household/cards/terms/review', { signal }),
  })
  const decision = useMutation({
    mutationFn: ({
      proposal,
      accept,
    }: {
      proposal: TermProposal
      accept: boolean
    }) =>
      post(`/api/household/cards/terms/review/${proposal.id}`, {
        fingerprint: proposal.fingerprint,
        accept,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['cards'] }),
  })
  if (!query.isError && !query.data?.length) return null
  return (
    <SectionCard
      title="Card terms to verify"
      description="Research stays separate from the plan until its source and terms have been checked."
    >
      {query.isError ? (
        <Button variant="outline" onClick={() => void query.refetch()}>
          Retry term reviews
        </Button>
      ) : null}
      {decision.error ? (
        <p role="alert" className="text-sm text-loss">
          {decision.error.message}
        </p>
      ) : null}
      <div className="space-y-4">
        {query.data?.map((proposal) => (
          <details
            key={proposal.id}
            className="rounded-xl border border-border/40 p-3"
          >
            <summary className="cursor-pointer font-medium">
              {proposal.productSlug} ·{' '}
              {Object.keys(proposal.proposedFields).length} proposed terms
            </summary>
            <dl className="my-3 space-y-3 text-sm">
              {Object.entries(proposal.proposedFields).map(([key, value]) => (
                <div key={key}>
                  <dt className="font-medium">
                    {key.replace(/([A-Z])/g, ' $1')}
                  </dt>
                  <dd className="break-words text-text-muted">
                    {termValue(proposal.previousFields[key])} →{' '}
                    {termValue(value)}
                  </dd>
                  <dd className="text-text-muted">
                    {proposal.evidence[key]?.excerpt ??
                      'Supporting terms missing; this change cannot be approved yet.'}
                  </dd>
                  {safeSource(proposal.evidence[key]?.sourceUrl) ? (
                    <dd>
                      <a
                        className="text-primary underline"
                        href={safeSource(proposal.evidence[key].sourceUrl)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Check issuer terms
                      </a>
                    </dd>
                  ) : null}
                </div>
              ))}
            </dl>
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={
                  decision.isPending ||
                  Object.keys(proposal.proposedFields).some(
                    (key) =>
                      !safeSource(proposal.evidence[key]?.sourceUrl) ||
                      !proposal.evidence[key]?.excerpt,
                  )
                }
                onClick={() => decision.mutate({ proposal, accept: true })}
              >
                I checked these terms · apply
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={decision.isPending}
                onClick={() => decision.mutate({ proposal, accept: false })}
              >
                Dismiss
              </Button>
            </div>
          </details>
        ))}
      </div>
    </SectionCard>
  )
}
