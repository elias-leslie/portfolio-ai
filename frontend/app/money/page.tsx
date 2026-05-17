'use client'

export const dynamic = 'force-dynamic'

import { Database, Loader2, PlusCircle, Settings2 } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { HouseholdDocumentCenter } from '@/components/money/HouseholdDocumentCenter'
import {
  HouseholdPlanningPanels,
  type PlanningFocusSection,
} from '@/components/money/HouseholdPlanningPanels'
import { JennyQuestionInbox } from '@/components/money/JennyQuestionInbox'
import { MoneyAccountsPanel } from '@/components/money/MoneyAccountsPanel'
import { MoneyAssumptionsDrawer } from '@/components/money/MoneyAssumptionsDrawer'
import { MoneyBudgetPanel } from '@/components/money/MoneyBudgetPanel'
import { MoneyDataServicesDrawer } from '@/components/money/MoneyDataServicesDrawer'
import { MoneyLedgerPanel } from '@/components/money/MoneyLedgerPanel'
import { MoneyLeversPanel } from '@/components/money/MoneyLeversPanel'
import { MoneyOverviewPanel } from '@/components/money/MoneyOverviewPanel'
import { MoneyRetirementPanel } from '@/components/money/MoneyRetirementPanel'
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
import {
  useHouseholdDashboard,
  useHouseholdDocuments,
  useHouseholdFacts,
} from '@/lib/hooks/useHousehold'
import { cn } from '@/lib/utils'

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

function MoneyWorkspaceSkeleton() {
  const tabLabels = [
    'Dashboard',
    'Budget',
    'Levers',
    'Retirement',
    'Allocation',
    'Accounts',
    'Ledger',
    'Intake',
    'Review',
  ]
  return (
    <div className="space-y-6" role="status" aria-live="polite">
      <span className="sr-only">Loading money workspace</span>
      <div className="rounded-2xl border border-border/40 bg-bg p-3 shadow-sm">
        <div className="flex flex-wrap gap-2">
          {tabLabels.map((label, idx) => (
            <div
              key={label}
              className={cn(
                'h-10 rounded-xl border border-border/30 bg-surface/50 px-4',
                idx === 0 ? 'w-28 animate-pulse bg-primary/10' : 'w-24',
                idx > 0 && 'skeleton',
              )}
            />
          ))}
        </div>
      </div>
      <div className="space-y-4">
        <div className="h-44 rounded-3xl skeleton" />
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="h-56 rounded-3xl skeleton" />
          <div className="h-56 rounded-3xl skeleton" />
        </div>
      </div>
    </div>
  )
}

type MoneyUtility = 'planning' | 'data-services'
type MoneyFocus =
  | 'date-quality'
  | 'clarifications'
  | 'account-coverage'
  | 'discovered-accounts'
  | PlanningFocusSection
type MoneyIntent = 'evidence' | 'review'

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
  return requested === 'planning' || requested === 'data-services'
    ? requested
    : null
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
    requested === 'clarifications' ||
    requested === 'account-coverage' ||
    requested === 'discovered-accounts' ||
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

function resolveRequestedIntent(
  requested: string | null | undefined,
): MoneyIntent | null {
  return requested === 'evidence' || requested === 'review' ? requested : null
}

function readRequestedIntent(): MoneyIntent | null {
  if (typeof window === 'undefined') {
    return null
  }

  return resolveRequestedIntent(
    new URLSearchParams(window.location.search).get('intent'),
  )
}

function readRequestedAccountId(): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  return new URLSearchParams(window.location.search).get('account')
}

function readRequestedQuestionId(): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  return new URLSearchParams(window.location.search).get('question')
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

function MoneyPageContent() {
  const [openUtility, setOpenUtilityState] = useState<MoneyUtility | null>(
    readRequestedUtility,
  )
  const [focusedReview, setFocusedReview] = useState<MoneyFocus | null>(
    readRequestedFocus,
  )
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(
    readRequestedAccountId,
  )
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(
    readRequestedQuestionId,
  )
  const [selectedIntent, setSelectedIntent] = useState<MoneyIntent | null>(
    readRequestedIntent,
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
  const { data: facts = [] } = useHouseholdFacts()
  useEffect(() => {
    const syncFromLocation = () => {
      const currentUrl = new URL(window.location.href)
      const currentUtility = currentUrl.searchParams.get('utility')
      if (currentUtility === 'evidence') {
        currentUrl.searchParams.delete('utility')
        currentUrl.searchParams.set('tab', 'intake')
        window.history.replaceState(window.history.state, '', currentUrl)
      }
      const requestedFocus = readRequestedFocus()
      setFocusedReview((current) =>
        current === requestedFocus ? current : requestedFocus,
      )
      setOpenUtilityState((current) => {
        const requested = readRequestedUtility()
        return current === requested ? current : requested
      })
      const requestedAccountId = readRequestedAccountId()
      setSelectedAccountId((current) =>
        current === requestedAccountId ? current : requestedAccountId,
      )
      const requestedIntent = readRequestedIntent()
      setSelectedIntent((current) =>
        current === requestedIntent ? current : requestedIntent,
      )
      const requestedQuestionId = readRequestedQuestionId()
      setSelectedQuestionId((current) =>
        current === requestedQuestionId ? current : requestedQuestionId,
      )
    }

    window.addEventListener('locationchange', syncFromLocation)
    window.addEventListener('popstate', syncFromLocation)
    syncFromLocation()

    return () => {
      window.removeEventListener('locationchange', syncFromLocation)
      window.removeEventListener('popstate', syncFromLocation)
    }
  }, [])

  const setOpenUtility = (nextUtility: MoneyUtility | null) => {
    const nextFocus =
      nextUtility === 'planning' && isPlanningFocus(focusedReview)
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
        <MoneyWorkspaceSkeleton />
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
      documentRequirements={[]}
      dateQualityIssues={
        focusedReview === 'date-quality' ? dashboard.transactionDateIssues : []
      }
      moneyInbox={[]}
      focusedReview={focusedReview === 'date-quality'}
    />
  )

  const tabs: WorkspaceTab[] = [
    {
      value: 'dashboard',
      label: 'Dashboard',
      content: (
        <div className="space-y-6">
          <MoneyOverviewPanel dashboard={dashboard} sections={['decision']} />
        </div>
      ),
    },
    {
      value: 'spending',
      label: 'Budget',
      content: <MoneyBudgetPanel />,
    },
    {
      value: 'levers',
      label: 'Levers',
      content: (
        <MoneyLeversPanel
          priceInsights={dashboard.reports.priceInsights ?? []}
        />
      ),
    },
    {
      value: 'retirement',
      label: 'Retirement',
      content: (
        <MoneyRetirementPanel
          dashboard={dashboard}
          onEditTargets={() => {
            setFocusedReview('retirement')
            setOpenUtility('planning')
          }}
        />
      ),
    },
    {
      value: 'allocation',
      label: 'Allocation',
      content: (
        <div className="space-y-6">
          <MoneyOverviewPanel dashboard={dashboard} sections={['allocation']} />
        </div>
      ),
    },
    {
      value: 'accounts',
      label: 'Accounts',
      badge:
        dashboard.overview.trackedAccountCount > 0
          ? String(dashboard.overview.trackedAccountCount)
          : undefined,
      content: (
        <div className="space-y-6">
          <MoneyAccountsPanel
            accounts={dashboard.accounts}
            discoveredAccounts={dashboard.discoveredAccounts}
            documents={documentItems}
            focus={
              focusedReview === 'account-coverage'
                ? 'coverage'
                : focusedReview === 'discovered-accounts'
                  ? 'discovered'
                  : null
            }
            selectedAccountId={selectedAccountId}
            intent={selectedIntent}
          />
        </div>
      ),
    },
    {
      value: 'ledger',
      label: 'Ledger',
      content: <MoneyLedgerPanel />,
    },
    {
      value: 'intake',
      label: 'Intake',
      content: intakeContent,
    },
    {
      value: 'review',
      label: 'Review',
      content: (
        <div id="money-clarifications" className="space-y-6">
          <SectionCard
            variant="surface"
            title="Review"
            description="Targeted follow-up tools. Today owns the queue; this tab handles the selected drill-down."
          >
            {focusedReview === 'clarifications' || selectedQuestionId ? (
              <JennyQuestionInbox
                questions={openQuestions}
                title="Clarifications"
                description="Resolve the targeted clarification, then return to Today."
                selectedQuestionId={selectedQuestionId}
              />
            ) : (
              <p className="text-sm text-text-muted">
                Use Today → Action Queue to open a specific clarification or
                data-quality review.
              </p>
            )}
          </SectionCard>
        </div>
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
              onClick={() => setOpenUtility('data-services')}
            >
              <Database className="mr-2 h-4 w-4" />
              Data services
            </Button>
            <Button asChild type="button" variant="outline" size="sm">
              <Link href="/money?tab=intake">
                <PlusCircle className="mr-2 h-4 w-4" />
                Add anything
              </Link>
            </Button>
          </div>
        }
      />

      <WorkspaceTabs
        defaultValue="dashboard"
        ariaLabel="Money workspace sections"
        tabs={tabs}
      />

      <Dialog
        open={openUtility === 'planning'}
        onOpenChange={(open) => setOpenUtility(open ? 'planning' : null)}
      >
        <DialogContent className="left-auto right-0 top-0 h-dvh max-w-[min(980px,100vw)] translate-x-0 translate-y-0 rounded-none border-l border-border/45 p-0 sm:max-w-[min(980px,100vw)]">
          <div className="max-h-dvh overflow-y-auto p-6">
            <DialogHeader>
              <DialogTitle>Assumptions</DialogTitle>
              <DialogDescription>
                Confirm what Jenny found, override it when needed, and keep the
                manual finance inputs in one minimal workspace.
              </DialogDescription>
            </DialogHeader>
            <div className="mt-4">
              <MoneyAssumptionsDrawer
                profile={dashboard.profile}
                resolvedValues={dashboard.resolvedValues}
                facts={facts}
                planningContent={
                  isPlanningFocus(focusedReview) &&
                  focusedReview !== 'income' &&
                  focusedReview !== 'retirement' ? (
                    <HouseholdPlanningPanels
                      dashboard={dashboard}
                      focusedSection={focusedReview}
                    />
                  ) : undefined
                }
              />
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={openUtility === 'data-services'}
        modal={false}
        onOpenChange={(open) => setOpenUtility(open ? 'data-services' : null)}
      >
        <DialogContent className="left-auto right-0 top-0 h-dvh max-w-[min(1040px,100vw)] translate-x-0 translate-y-0 rounded-none border-l border-border/45 p-0 sm:max-w-[min(1040px,100vw)]">
          <div className="max-h-dvh overflow-y-auto p-6">
            <DialogHeader>
              <DialogTitle>Data Services</DialogTitle>
              <DialogDescription>
                External financial data connections for household accounts,
                balances, positions, activities, and transactions.
              </DialogDescription>
            </DialogHeader>
            <div className="mt-4">
              <MoneyDataServicesDrawer />
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </PageContainer>
  )
}

export default function MoneyPage() {
  return <MoneyPageContent />
}
