'use client'

export const dynamic = 'force-dynamic'

import { Database, PlusCircle, Settings2 } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { MoneyCardsPanel } from '@/components/money/cards/MoneyCardsPanel'
import { HouseholdDocumentCenter } from '@/components/money/HouseholdDocumentCenter'
import { JennyQuestionInbox } from '@/components/money/JennyQuestionInbox'
import { MoneyAccountsPanel } from '@/components/money/MoneyAccountsPanel'
import { MoneyBudgetPanel } from '@/components/money/MoneyBudgetPanel'
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
  useHouseholdDashboard,
  useHouseholdDocuments,
  useHouseholdFacts,
} from '@/lib/hooks/useHousehold'
import {
  LoadingState,
  MoneyWorkspaceSkeleton,
} from './_components/MoneySkeletons'
import { MoneyUtilityDrawers } from './_components/MoneyUtilityDrawers'
import {
  isPlanningFocus,
  type MoneyFocus,
  type MoneyRouteState,
  type MoneyUtility,
  readMoneyRouteState,
  resolveMoneyRouteState,
  syncUtilityToLocation,
} from './_components/money-route-state'

function MoneyPageContent() {
  const [routeState, setRouteState] =
    useState<MoneyRouteState>(readMoneyRouteState)
  const {
    openUtility,
    focusedReview,
    selectedAccountId,
    selectedQuestionId,
    selectedIntent,
  } = routeState

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

      const nextRouteState = resolveMoneyRouteState(currentUrl.searchParams)
      setRouteState((current) =>
        current.openUtility === nextRouteState.openUtility &&
        current.focusedReview === nextRouteState.focusedReview &&
        current.selectedAccountId === nextRouteState.selectedAccountId &&
        current.selectedQuestionId === nextRouteState.selectedQuestionId &&
        current.selectedIntent === nextRouteState.selectedIntent
          ? current
          : nextRouteState,
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
    const nextFocus: MoneyFocus | null =
      nextUtility === 'planning' && isPlanningFocus(focusedReview)
        ? focusedReview
        : null
    setRouteState((current) => ({
      ...current,
      openUtility: nextUtility,
      focusedReview: nextFocus,
    }))
    syncUtilityToLocation(nextUtility, nextFocus)
  }

  // Only the dashboard-dependent tabs need the dashboard payload. Budget, Levers,
  // and Ledger fetch their own data, so a slow dashboard query must not blank them —
  // we render the workspace shell and let each tab resolve its own loading state.
  if (error && !dashboard) {
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

  const dashboardFallback = isLoading ? (
    <MoneyWorkspaceSkeleton />
  ) : (
    <LoadingState />
  )
  const documentItems = documents?.items ?? []
  const openQuestions = dashboard?.questions.filter((q) => !q.answeredAt) ?? []

  const intakeContent = documentsError ? (
    <LoadErrorState
      title="Failed to load intake documents."
      detail="Retry to refresh the intake queue and uploaded household files."
      onRetry={() => {
        void refetchDocuments()
      }}
      isRetrying={isFetchingDocuments}
    />
  ) : !dashboard || (!documents && isFetchingDocuments) ? (
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
      content: dashboard ? (
        <div className="space-y-6">
          <MoneyOverviewPanel dashboard={dashboard} sections={['decision']} />
        </div>
      ) : (
        dashboardFallback
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
          priceInsights={dashboard?.reports.priceInsights ?? []}
        />
      ),
    },
    {
      value: 'cards',
      label: 'Cards',
      content: <MoneyCardsPanel dashboard={dashboard ?? undefined} />,
    },
    {
      value: 'retirement',
      label: 'Retirement',
      content: dashboard ? (
        <MoneyRetirementPanel
          dashboard={dashboard}
          onEditTargets={() => {
            setRouteState((current) => ({
              ...current,
              focusedReview: 'retirement',
              openUtility: 'planning',
            }))
            syncUtilityToLocation('planning', 'retirement')
          }}
        />
      ) : (
        dashboardFallback
      ),
    },
    {
      value: 'allocation',
      label: 'Allocation',
      content: dashboard ? (
        <div className="space-y-6">
          <MoneyOverviewPanel dashboard={dashboard} sections={['allocation']} />
        </div>
      ) : (
        dashboardFallback
      ),
    },
    {
      value: 'accounts',
      label: 'Accounts',
      badge:
        dashboard && dashboard.overview.trackedAccountCount > 0
          ? String(dashboard.overview.trackedAccountCount)
          : undefined,
      content: dashboard ? (
        <div className="space-y-6">
          <MoneyAccountsPanel
            accounts={dashboard.accounts}
            accountControl={dashboard.accountControl}
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
      ) : (
        dashboardFallback
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

      {dashboard ? (
        <MoneyUtilityDrawers
          openUtility={openUtility}
          focusedReview={focusedReview}
          dashboard={dashboard}
          facts={facts}
          onUtilityChange={setOpenUtility}
        />
      ) : null}
    </PageContainer>
  )
}

export default function MoneyPage() {
  return <MoneyPageContent />
}
