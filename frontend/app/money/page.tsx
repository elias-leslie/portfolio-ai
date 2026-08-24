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
import { MoneyPurchasesPanel } from '@/components/money/MoneyPurchasesPanel'
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
  useHouseholdNetWorthTrend,
} from '@/lib/hooks/useHousehold'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
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
  const { data: analytics } = usePortfolioAnalytics()
  const { data: netWorthTrend } = useHouseholdNetWorthTrend({ days: 180 })
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
      const currentTab = currentUrl.searchParams.get('tab')
      if (currentUtility === 'evidence') {
        currentUrl.searchParams.delete('utility')
        currentUrl.searchParams.set('tab', 'intake')
        window.history.replaceState(window.history.state, '', currentUrl)
      }
      if (currentTab === 'review') {
        currentUrl.searchParams.set('tab', 'intake')
        if (!currentUrl.searchParams.get('focus')) {
          currentUrl.searchParams.set('focus', 'clarifications')
        }
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
  // and Ledger fetch their own data, so a dashboard failure must not blank them.
  const dashboardFallback =
    error && !dashboard ? (
      <LoadErrorState
        title="Dashboard data is unavailable."
        detail="Budget, Levers, and Ledger remain available. Retry to restore the overview, retirement, account, intake, and review data."
        onRetry={() => {
          void refetchDashboard()
        }}
        isRetrying={isFetchingDashboard}
        retryLabel="Retry dashboard"
        className="rounded-3xl p-8"
      />
    ) : isLoading ? (
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
  ) : !dashboard ? (
    dashboardFallback
  ) : !documents && isFetchingDocuments ? (
    <LoadingState />
  ) : (
    <HouseholdDocumentCenter
      documents={documentItems}
      importCenter={dashboard.importCenter}
      dateQualityIssues={dashboard.transactionDateIssues}
      focusedReview={focusedReview === 'date-quality'}
    />
  )

  const tabs: WorkspaceTab[] = [
    {
      value: 'dashboard',
      label: 'Dashboard',
      content: dashboard ? (
        <div className="space-y-6">
          {/* The Decision Board's four cards and the allocation donut are gone
              from here: the month's verdict, Free to spend, the needs/wants
              split and the review queue all live on the Budget tab now, where
              the household is actually reading the month, and allocation is an
              Investing question. What is left is what the money is, and what
              is about to leave it. */}
          <MoneyOverviewPanel
            dashboard={dashboard}
            analytics={analytics}
            netWorthTrend={netWorthTrend}
            sections={['tiles', 'commitments']}
          />
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
      value: 'purchases',
      label: 'Purchases',
      content: (
        <MoneyPurchasesPanel
          priceInsights={dashboard?.reports.priceInsights ?? []}
        />
      ),
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
      label: 'Intake & Review',
      content: (
        <div className="space-y-6">
          {intakeContent}
          {dashboard ? (
            <div id="money-clarifications" className="space-y-6">
              <SectionCard
                variant="surface"
                title="Clarifications & Review"
                description="Targeted follow-up questions and data-quality reviews."
              >
                {openQuestions.length > 0 ||
                focusedReview === 'clarifications' ||
                selectedQuestionId ? (
                  <JennyQuestionInbox
                    questions={openQuestions}
                    title="Clarifications"
                    description="Resolve the targeted clarification, then return to Today."
                    selectedQuestionId={selectedQuestionId}
                  />
                ) : (
                  <p className="text-sm text-text-muted">
                    No open clarification questions right now. Use Today →
                    Action Queue to view active items.
                  </p>
                )}
              </SectionCard>
            </div>
          ) : null}
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
