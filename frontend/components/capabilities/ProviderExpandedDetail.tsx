'use client'

import { ExternalLink, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { SourceDetail, SourceProvider } from '@/lib/api/sources'

interface ProviderExpandedDetailProps {
  provider: SourceProvider
  detail: SourceDetail | null | undefined
  detailLoading: boolean
}

export function ProviderExpandedDetail({
  provider,
  detail,
  detailLoading,
}: ProviderExpandedDetailProps) {
  return (
    <div className="border-t border-border p-4 bg-surface-muted/30">
      {detailLoading ? (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : detail ? (
        <div className="space-y-4">
          {/* Use Cases */}
          <div>
            <h4 className="text-sm font-medium text-foreground mb-2">
              Best For
            </h4>
            <div className="flex flex-wrap gap-2">
              {(detail.useCases ?? []).map((useCase, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {useCase}
                </Badge>
              ))}
            </div>
          </div>

          {/* GAP Coverage Details */}
          {(provider.gapCoverage?.length ?? 0) > 0 && (
            <div>
              <h4 className="text-sm font-medium text-foreground mb-2">
                GAP Coverage
              </h4>
              <div className="flex flex-wrap gap-2">
                {provider.gapCoverage?.map((gap) => (
                  <Badge
                    key={gap}
                    variant="outline"
                    className="bg-accent/10 text-accent border-accent/20"
                  >
                    {gap}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Endpoints */}
          <div>
            <h4 className="text-sm font-medium text-foreground mb-2">
              Endpoints ({Object.keys(detail.endpoints ?? {}).length})
            </h4>
            <div className="grid gap-2">
              {Object.entries(detail.endpoints ?? {}).map(
                ([name, endpoint]) => (
                  <div
                    key={name}
                    className="rounded border border-border bg-surface p-3"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <code className="text-sm font-mono text-foreground">
                          {endpoint.path || endpoint.method || name}
                        </code>
                        {endpoint.gapId && (
                          <Badge
                            variant="outline"
                            className="ml-2 text-xs bg-accent/10 text-accent"
                          >
                            {endpoint.gapId}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {endpoint.description}
                    </p>
                    {endpoint.notes && (
                      <p className="text-xs text-muted-foreground mt-1 italic">
                        {endpoint.notes}
                      </p>
                    )}
                  </div>
                ),
              )}
            </div>
          </div>

          {/* Premium Only */}
          {(detail.premiumOnly?.length ?? 0) > 0 && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2">
                Premium Only (Not Available)
              </h4>
              <div className="flex flex-wrap gap-2">
                {(detail.premiumOnly ?? []).map((endpoint, i) => (
                  <Badge
                    key={i}
                    variant="outline"
                    className="text-xs text-muted-foreground"
                  >
                    {endpoint}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Implementation File */}
          {detail.implementationFile && (
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <ExternalLink className="h-3 w-3" />
              {detail.implementationFile}
            </div>
          )}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">
          No details available
        </div>
      )}
    </div>
  )
}
