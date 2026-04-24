'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { ThesisDecisionEligibility } from '@/lib/api/thesis'
import { fetchThesis, generateThesis, invalidateThesis } from '@/lib/api/thesis'
import { formatTimestamp } from './ExpandedRowUtils'
import { ActionBadge } from './thesis/ActionBadge'
import { ClaudeValidationSection } from './thesis/ClaudeValidationSection'
import { CoreReasonsSection } from './thesis/CoreReasonsSection'
import { ExpectedReturnsSection } from './thesis/ExpectedReturnsSection'
import { KeyCatalystsSection } from './thesis/KeyCatalystsSection'
import { RisksSection } from './thesis/RisksSection'
import { StatusBadge } from './thesis/StatusBadge'
import { ValueDriversSection } from './thesis/ValueDriversSection'
import { VersionHistorySection } from './thesis/VersionHistorySection'

interface ThesisSectionProps {
  symbol: string
  userTimezone: string
}

function eligibilityBadgeLabel(status: ThesisDecisionEligibility['status']) {
  switch (status) {
    case 'invalidated':
      return 'Invalidated'
    case 'unavailable':
      return 'Unavailable'
    case 'review_required':
      return 'Review required'
    default:
      return 'Current'
  }
}

function ThesisEligibilityNotice({
  eligibility,
}: {
  eligibility: ThesisDecisionEligibility
}) {
  if (eligibility.eligible && eligibility.reasons.length === 0) {
    return null
  }

  return (
    <div className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-text">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="warning">
          {eligibilityBadgeLabel(eligibility.status)}
        </Badge>
        <p className="font-semibold">
          Do not treat this thesis as current decision evidence.
        </p>
      </div>
      {eligibility.reasons.length > 0 ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-relaxed text-text-muted">
          {eligibility.reasons.slice(0, 4).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

/**
 * Thesis System UI Component
 *
 * Displays investment thesis with:
 * - Action recommendation (BUY/HOLD/SELL)
 * - Cross-validation score
 * - Core reasons with confidence bars
 * - Key catalysts with impact badges
 * - Risks with severity badges
 * - Value drivers
 * - Expected returns
 * - Version history
 */
export function ThesisSection({ symbol, userTimezone }: ThesisSectionProps) {
  const [showAdmin, setShowAdmin] = useState(false)
  const queryClient = useQueryClient()

  // Fetch thesis data
  const { data, isLoading, error } = useQuery({
    queryKey: ['thesis', symbol],
    queryFn: () => fetchThesis(symbol),
  })

  // Generate thesis mutation
  const generateMutation = useMutation({
    mutationFn: (forceRegenerate: boolean) =>
      generateThesis(symbol, { forceRegenerate: forceRegenerate }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['thesis', symbol] })
    },
  })

  // Invalidate thesis mutation
  const invalidateMutation = useMutation({
    mutationFn: (reason: string) => invalidateThesis(symbol, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['thesis', symbol] })
    },
  })

  if (isLoading) {
    return (
      <Card className="border-border">
        <CardContent className="p-6">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="border-border border-loss/20">
        <CardContent className="p-6">
          <p className="text-sm text-loss">
            Error loading thesis:{' '}
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </CardContent>
      </Card>
    )
  }

  const thesis = data?.thesis
  const eligibility = data?.decisionEligibility

  // No thesis exists
  if (!thesis) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="text-base">Investment Thesis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-text-muted">
            No thesis generated for {symbol}
          </p>
          <Button
            onClick={() => generateMutation.mutate(false)}
            disabled={generateMutation.isPending}
            aria-busy={generateMutation.isPending}
            size="sm"
          >
            {generateMutation.isPending ? 'Generating...' : 'Generate Thesis'}
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <TooltipProvider delayDuration={200}>
      <Card className="border-border">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Investment Thesis</CardTitle>
            <div className="flex items-center gap-2">
              <ActionBadge action={thesis.action} />
              {thesis.crossValidationScore !== null && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="cursor-help">
                      Cross-Val:{' '}
                      {(thesis.crossValidationScore * 100).toFixed(0)}%
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs">
                      AI cross-validation confidence score
                    </p>
                  </TooltipContent>
                </Tooltip>
              )}
              <StatusBadge status={thesis.status} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {eligibility ? (
            <ThesisEligibilityNotice eligibility={eligibility} />
          ) : null}

          {/* Core Reasons */}
          <CoreReasonsSection reasons={thesis.coreReasons} />

          {/* Key Catalysts */}
          {thesis.keyCatalysts.length > 0 && (
            <KeyCatalystsSection
              catalysts={thesis.keyCatalysts}
              userTimezone={userTimezone}
            />
          )}

          {/* Risks */}
          {thesis.risks.length > 0 && <RisksSection risks={thesis.risks} />}

          {/* Value Drivers */}
          {thesis.valueDrivers && (
            <ValueDriversSection drivers={thesis.valueDrivers} />
          )}

          {/* Expected Returns */}
          {(thesis.expectedReturnPct !== null ||
            thesis.expectedTimeframeDays !== null) && (
            <ExpectedReturnsSection thesis={thesis} />
          )}

          {/* Claude Validation */}
          {thesis.claudeValidation && (
            <ClaudeValidationSection validation={thesis.claudeValidation} />
          )}

          {/* Version History */}
          {data.versions && data.versions.length > 1 && (
            <VersionHistorySection
              versions={data.versions}
              userTimezone={userTimezone}
            />
          )}

          {/* Action Buttons */}
          <div className="border-t border-border pt-3 flex items-center gap-2">
            <Button
              onClick={() => generateMutation.mutate(true)}
              disabled={generateMutation.isPending}
              aria-busy={generateMutation.isPending}
              size="sm"
              variant="outline"
            >
              {generateMutation.isPending ? 'Regenerating...' : 'Regenerate'}
            </Button>
            <Button
              onClick={() => setShowAdmin(!showAdmin)}
              size="sm"
              variant="ghost"
            >
              {showAdmin ? 'Hide Admin' : 'Admin'}
            </Button>
            {showAdmin && (
              <Button
                onClick={() =>
                  invalidateMutation.mutate('Manual invalidation by user')
                }
                disabled={invalidateMutation.isPending}
                aria-busy={invalidateMutation.isPending}
                size="sm"
                variant="destructive"
              >
                {invalidateMutation.isPending
                  ? 'Invalidating...'
                  : 'Invalidate'}
              </Button>
            )}
            <div className="ml-auto text-xs text-text-muted">
              v{thesis.version} • Updated{' '}
              {formatTimestamp(thesis.updatedAt, userTimezone)}
            </div>
          </div>
        </CardContent>
      </Card>
    </TooltipProvider>
  )
}
