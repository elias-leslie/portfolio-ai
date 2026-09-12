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
import { MoneyOverviewPanel } from '@/components/money/MoneyOverviewPanel'
import { MoneyPurchasesPanel } from '@/components/money/MoneyPurchasesPanel'
import { MoneyRetirementPanel } from '@/components/money/MoneyRetirementPanel'
import { useMoneyQuery } from '@/components/money/useMoneyQuery'
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

  const [activeTab] = useMoneyQuery('tab', 'spending')
  const needsDashboard =
    ['dashboard', 'retirement', 'accounts', 'intake'].includes(activeTab) ||
    openUtility === 'planning'
  const {
    data: dashboard,
    isLoading,
    error,
    refetch: refetchDashboard,
    isFetching: isFetchingDashboard,
  } = useHouseholdDashboard({ enabled: needsDashboard })
  const { data: analytics } = usePortfolioAnalytics({
    enabled: activeTab === 'dashboard',
  })
  const { data: netWorthTrend } = useHouseholdNetWorthTrend(
    { days: 180 },
    { enabled: activeTab === 'dashboard' },
  )
  const {
    data: documents,
    error: documentsError,
    isLoading: documentsLoading,
    refetch: refetchDocuments,
  } = useHouseholdDocuments({
    enabled: activeTab === 'accounts',
  })
  const { data: facts = [] } = useHouseholdFacts({
    enabled: activeTab === 'retirement' || openUtility === 'planning',
  })

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

  // Only the dashboard-dependent tabs need the dashboard payload. Review
  // and Ledger fetch their own data, so a dashboard failure must not blank them.
  const dashboardFallback =
    error && !dashboard ? (
      <LoadErrorState
        title="Dashboard data is unavailable."
        detail="Review and Ledger remain available. Retry to restore net worth, retirement, and account data."
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

  const intakeContent = (
    <HouseholdDocumentCenter
      importCenter={dashboard?.importCenter}
      dateQualityIssues={dashboard?.transactionDateIssues}
      focusedReview={focusedReview === 'date-quality'}
    />
  )

  const tabs: WorkspaceTab[] = [
    {
      value: 'dashboard',
      label: 'Net worth',
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
      label: 'Review',
      content: <MoneyBudgetPanel />,
    },
    {
      value: 'purchases',
      label: 'Purchases',
      content: <MoneyPurchasesPanel />,
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
          facts={facts}
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
          {documentsLoading && (
            <p role="status" className="text-sm text-text-muted">
              Loading account evidence…
            </p>
          )}
          {documentsError && (
            <LoadErrorState
              title="Account evidence could not be loaded."
              onRetry={() => void refetchDocuments()}
            />
          )}
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
      content: (
        <div className="space-y-6">
          {intakeContent}
          {dashboard ? (
            <div
              id="money-clarifications"
              className="scroll-mt-64 space-y-6 md:scroll-mt-48"
            >
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
    <PageContainer className="space-y-4 py-4 sm:space-y-6 sm:py-8">
      <PageHeader
        size="sm"
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
              <Link href="/money?tab=intake#add-evidence-upload">
                <PlusCircle className="mr-2 h-4 w-4" />
                Add anything
              </Link>
            </Button>
          </div>
        }
      />

      <WorkspaceTabs
        defaultValue="spending"
        ariaLabel="Money workspace sections"
        tabs={tabs}
      />

      <MoneyUtilityDrawers
        openUtility={openUtility}
        focusedReview={focusedReview}
        dashboard={dashboard}
        dashboardFallback={dashboardFallback}
        facts={facts}
        onUtilityChange={setOpenUtility}
      />
    </PageContainer>
  )
}

export default function MoneyPage() {
  return <MoneyPageContent />
}
