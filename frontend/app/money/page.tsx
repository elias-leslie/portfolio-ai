'use client'

import { Loader2, PlusCircle, Settings2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { HouseholdDocumentCenter } from '@/components/money/HouseholdDocumentCenter'
import {
  HouseholdPlanningPanels,
  type PlanningFocusSection,
} from '@/components/money/HouseholdPlanningPanels'
import { HouseholdProfileCard } from '@/components/money/HouseholdProfileCard'
import { JennyQuestionInbox } from '@/components/money/JennyQuestionInbox'
import { MoneyAccountsPanel } from '@/components/money/MoneyAccountsPanel'
import { MoneyOverviewPanel } from '@/components/money/MoneyOverviewPanel'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import type { WorkspaceTab } from '@/components/shared/WorkspaceTabs'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { formatCurrencyWhole } from '@/lib/formatters'
import {
  useHouseholdDashboard,
  useHouseholdDocuments,
} from '@/lib/hooks/useHousehold'

function LoadingState() {
  return (
    <div
      className="flex min-h-72 items-center justify-center rounded-3xl border border-border/40 bg-surface-muted/20"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-3 text-sm font-medium text-text-muted">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        Loading money workspace...
      </div>
    </div>
  )
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail: string
}) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface/60 px-4 py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-text">
        {value}
      </p>
      <p className="mt-1 text-sm leading-relaxed text-text-muted">{detail}</p>
    </div>
  )
}

type MoneyUtility = 'evidence' | 'planning'
type MoneyFocus = 'date-quality' | 'account-coverage' | PlanningFocusSection

const planningFocusSections = new Set<string>([
  'household',
  'income',
  'debt',
  'housing',
  'insurance',
  'retirement',
  'expenses',
])

function isPlanningFocus(
  focus: MoneyFocus | null,
): focus is PlanningFocusSection {
  return Boolean(focus && planningFocusSections.has(focus))
}

function resolveRequestedUtility(
  requested: string | null | undefined,
): MoneyUtility | null {
  return requested === 'evidence' || requested === 'planning' ? requested : null
}

function readRequestedUtility(): MoneyUtility | null {
  if (typeof window === 'undefined') {
    return null
  }

  return resolveRequestedUtility(
    new URLSearchParams(window.location.search).get('utility'),
  )
}

function resolveRequestedFocus(
  requested: string | null | undefined,
): MoneyFocus | null {
  if (
    requested === 'date-quality' ||
    requested === 'account-coverage' ||
    planningFocusSections.has(requested ?? '')
  ) {
    return requested as MoneyFocus
  }
  return null
}

function readRequestedFocus(): MoneyFocus | null {
  if (typeof window === 'undefined') {
    return null
  }

  return resolveRequestedFocus(
    new URLSearchParams(window.location.search).get('focus'),
  )
}

function syncUtilityToLocation(
  nextUtility: MoneyUtility | null,
  nextFocus: MoneyFocus | null = null,
) {
  if (typeof window === 'undefined') {
    return
  }

  const nextUrl = new URL(window.location.href)
  if (nextUtility) {
    nextUrl.searchParams.set('utility', nextUtility)
  } else {
    nextUrl.searchParams.delete('utility')
  }
  if (nextUtility && nextFocus) {
    nextUrl.searchParams.set('focus', nextFocus)
  } else {
    nextUrl.searchParams.delete('focus')
  }
  window.history.replaceState(window.history.state, '', nextUrl)
}

export default function MoneyPage() {
  const [openUtility, setOpenUtilityState] = useState<MoneyUtility | null>(
    readRequestedUtility,
  )
  const [focusedReview, setFocusedReview] = useState<MoneyFocus | null>(
    readRequestedFocus,
  )
  const {
    data: dashboard,
    isLoading,
    error,
    refetch: refetchDashboard,
    isFetching: isFetchingDashboard,
  } = useHouseholdDashboard()
  const {
    data: documents,
    error: documentsError,
    refetch: refetchDocuments,
    isFetching: isFetchingDocuments,
  } = useHouseholdDocuments()

  useEffect(() => {
    const syncFromLocation = () => {
      const requestedFocus = readRequestedFocus()
      setFocusedReview((current) =>
        current === requestedFocus ? current : requestedFocus,
      )
      setOpenUtilityState((current) => {
        const requested = readRequestedUtility()
        return current === requested ? current : requested
      })
    }

    window.addEventListener('popstate', syncFromLocation)
    syncFromLocation()

    return () => {
      window.removeEventListener('popstate', syncFromLocation)
    }
  }, [])

  const setOpenUtility = (nextUtility: MoneyUtility | null) => {
    const nextFocus =
      nextUtility === 'evidence' && focusedReview === 'date-quality'
        ? focusedReview
        : nextUtility === 'planning' && isPlanningFocus(focusedReview)
          ? focusedReview
          : null
    setOpenUtilityState(nextUtility)
    setFocusedReview(nextFocus)
    syncUtilityToLocation(nextUtility, nextFocus)
  }

  if (isLoading) {
    return (
      <PageContainer className="space-y-6 py-8">
        <PageHeader eyebrow="Household Finance" title="Money" />
        <LoadingState />
      </PageContainer>
    )
  }

  if (!dashboard || error) {
    return (
      <PageContainer className="space-y-6 py-8">
        <PageHeader eyebrow="Household Finance" title="Money" />
        <LoadErrorState
          title="Failed to load the money workspace."
          detail="Retry to refresh the dashboard, account cards, and evidence coverage."
          onRetry={() => {
            void refetchDashboard()
          }}
          isRetrying={isFetchingDashboard}
          retryLabel="Retry workspace"
          className="rounded-3xl p-8"
        />
      </PageContainer>
    )
  }

  const documentItems = documents?.items ?? []
  const openQuestions = dashboard.questions.filter(
    (question) => !question.answeredAt,
  )
  const trackedDocuments =
    documentItems.length || dashboard.importCenter.trackedDocuments
  const metrics = [
    {
      label: 'Net Worth',
      value: formatCurrencyWhole(dashboard.overview.netWorth),
      detail: `${formatCurrencyWhole(dashboard.overview.totalTrackedAssets)} assets less ${formatCurrencyWhole(dashboard.overview.liabilitiesTotal)} liabilities.`,
    },
    {
      label: 'Monthly Spend',
      value: formatCurrencyWhole(
        dashboard.reports.executive.averageMonthlySpend,
      ),
      detail:
        dashboard.overview.coverageMonths > 0
          ? `${dashboard.overview.coverageMonths} month${dashboard.overview.coverageMonths === 1 ? '' : 's'} of recent evidence coverage.`
          : 'No recent statement coverage yet.',
    },
    {
      label: 'Freshness',
      value: `${dashboard.overview.visibilityScore}/100`,
      detail: `${dashboard.overview.visibilityLabel}. ${dashboard.overview.needsRefreshCount} stale account${dashboard.overview.needsRefreshCount === 1 ? '' : 's'}.`,
    },
    {
      label: 'Accounts',
      value: String(dashboard.overview.trackedAccountCount),
      detail: `${trackedDocuments} evidence file${trackedDocuments === 1 ? '' : 's'} · ${dashboard.overview.gapCount} active gap${dashboard.overview.gapCount === 1 ? '' : 's'}.`,
    },
  ]

  const intakeContent = documentsError ? (
    <LoadErrorState
      title="Failed to load intake documents."
      detail="Retry to refresh the intake queue and uploaded household files."
      onRetry={() => {
        void refetchDocuments()
      }}
      isRetrying={isFetchingDocuments}
    />
  ) : !documents && isFetchingDocuments ? (
    <LoadingState />
  ) : (
    <HouseholdDocumentCenter
      documents={documentItems}
      importCenter={dashboard.importCenter}
      documentRequirements={dashboard.planning?.documentRequirements ?? []}
      dateQualityIssues={dashboard.transactionDateIssues}
      focusedReview={focusedReview === 'date-quality'}
    />
  )

  const tabs: WorkspaceTab[] = [
    {
      value: 'dashboard',
      label: 'Dashboard',
      content: (
        <div className="space-y-6">
          {dashboard.accounts.length === 0 && documentItems.length === 0 ? (
            <SectionCard
              variant="surface"
              title="Get started"
              actions={
                <Button
                  type="button"
                  size="sm"
                  onClick={() => setOpenUtility('evidence')}
                >
                  <PlusCircle className="mr-2 h-4 w-4" />
                  Add anything
                </Button>
              }
            >
              <p className="text-sm text-text-muted">
                Upload a statement, screenshot, export, or bill and Jenny will
                classify it, attach it to the right account when possible, or
                create a new candidate when the account does not exist yet.
              </p>
            </SectionCard>
          ) : null}

          <MoneyOverviewPanel dashboard={dashboard} />

          {openQuestions.length > 0 ? (
            <div id="money-clarifications">
              <JennyQuestionInbox
                questions={openQuestions}
                title="Clarifications"
                description="Answer only the remaining gaps Jenny cannot infer safely."
              />
            </div>
          ) : null}
        </div>
      ),
    },
    {
      value: 'accounts',
      label: 'Accounts',
      badge:
        dashboard.overview.needsRefreshCount > 0
          ? String(dashboard.overview.needsRefreshCount)
          : undefined,
      content: (
        <MoneyAccountsPanel
          accounts={dashboard.accounts}
          documents={documentItems}
          focus={focusedReview === 'account-coverage' ? 'coverage' : null}
        />
      ),
    },
  ]

  return (
    <PageContainer className="space-y-6 py-8">
      <PageHeader
        eyebrow="Household Finance"
        title="Money"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setOpenUtility('planning')}
            >
              <Settings2 className="mr-2 h-4 w-4" />
              Assumptions
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setOpenUtility('evidence')}
            >
              <PlusCircle className="mr-2 h-4 w-4" />
              Add anything
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            detail={metric.detail}
          />
        ))}
      </div>

      <WorkspaceTabs
        defaultValue="dashboard"
        ariaLabel="Money workspace sections"
        tabs={tabs}
      />

      <Dialog
        open={openUtility === 'evidence'}
        onOpenChange={(open) => setOpenUtility(open ? 'evidence' : null)}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>Add anything</DialogTitle>
            <DialogDescription>
              Upload screenshots, statements, exports, or planning files in one
              place. Jenny uses the file itself to decide what it is, what
              matters, and which account or financial area it belongs to.
            </DialogDescription>
          </DialogHeader>
          {intakeContent}
        </DialogContent>
      </Dialog>

      <Dialog
        open={openUtility === 'planning'}
        onOpenChange={(open) => setOpenUtility(open ? 'planning' : null)}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>Assumptions</DialogTitle>
            <DialogDescription>
              Review the household profile, goals, and planning assumptions
              without adding another default page section.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <HouseholdProfileCard
              profile={dashboard.profile}
              resolvedValues={dashboard.resolvedValues}
            />
            <HouseholdPlanningPanels
              dashboard={dashboard}
              focusedSection={
                isPlanningFocus(focusedReview) ? focusedReview : null
              }
            />
          </div>
        </DialogContent>
      </Dialog>
    </PageContainer>
  )
}
