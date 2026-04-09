'use client'

import { Loader2 } from 'lucide-react'
import Link from 'next/link'
import { HouseholdDocumentCenter } from '@/components/money/HouseholdDocumentCenter'
import { HouseholdPlanningPanels } from '@/components/money/HouseholdPlanningPanels'
import { HouseholdProfileCard } from '@/components/money/HouseholdProfileCard'
import { MoneyAccountsPanel } from '@/components/money/MoneyAccountsPanel'
import { MoneyInboxPanel } from '@/components/money/MoneyInboxPanel'
import { MoneyOverviewPanel } from '@/components/money/MoneyOverviewPanel'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import type { WorkspaceTab } from '@/components/shared/WorkspaceTabs'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { formatCurrencyWhole } from '@/lib/formatters'
import {
  useHouseholdDashboard,
  useHouseholdDocuments,
} from '@/lib/hooks/useHousehold'
import { formatRelativeTime } from '@/lib/utils'

function LoadingState() {
  return (
    <div
      className="flex min-h-96 items-center justify-center rounded-3xl border border-border/40 bg-surface-muted/20"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-3 text-sm font-medium text-text-muted">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        Building your household finance workspace...
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
      <p className="mt-3 text-2xl font-semibold tracking-tight text-text">
        {value}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-text-muted">{detail}</p>
    </div>
  )
}

export default function MoneyPage() {
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

  if (isLoading) {
    return (
      <PageContainer className="space-y-10 py-10">
        <PageHeader
          eyebrow="Household Finance"
          title="Money System"
          description="One compact view of accounts, cash flow, evidence freshness, and what Jenny still needs."
        />
        <LoadingState />
      </PageContainer>
    )
  }

  if (!dashboard || error) {
    return (
      <PageContainer className="space-y-10 py-10">
        <PageHeader
          eyebrow="Household Finance"
          title="Money System"
          description="One compact view of accounts, cash flow, evidence freshness, and what Jenny still needs."
        />
        <LoadErrorState
          title="Failed to load the household finance workspace."
          detail="Retry to refresh the overview, account cards, and inbox."
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
  const trackedDocuments =
    documentItems.length || dashboard.importCenter.trackedDocuments
  const primaryInboxItem = dashboard.inbox[0] ?? null
  const metrics = [
    {
      label: 'Net Worth',
      value: formatCurrencyWhole(dashboard.overview.netWorth),
      detail: `${formatCurrencyWhole(dashboard.overview.totalTrackedAssets)} assets less ${formatCurrencyWhole(dashboard.overview.liabilitiesTotal)} liabilities.`,
    },
    {
      label: 'Cash',
      value: formatCurrencyWhole(dashboard.overview.cashReserve),
      detail: `${dashboard.overview.needsRefreshCount} account${dashboard.overview.needsRefreshCount === 1 ? '' : 's'} need fresher evidence.`,
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
      label: 'Accounts',
      value: String(dashboard.overview.trackedAccountCount),
      detail: `${dashboard.overview.candidateAccountCount} candidate${dashboard.overview.candidateAccountCount === 1 ? '' : 's'} still need confirmation.`,
    },
    {
      label: 'Inbox',
      value: String(dashboard.overview.inboxCount),
      detail: `${dashboard.overview.gapCount} explicit freshness or completeness gap${dashboard.overview.gapCount === 1 ? '' : 's'} surfaced.`,
    },
    {
      label: 'Evidence',
      value: String(trackedDocuments),
      detail: `${dashboard.importCenter.parsedDocuments} parsed · updated ${formatRelativeTime(dashboard.generatedAt)}`,
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
      evidenceAccounts={dashboard.evidenceAccounts}
    />
  )

  const tabs: WorkspaceTab[] = [
    {
      value: 'overview',
      label: 'Overview',
      description:
        'Start here for the visual summary, then drill into the accounts or categories behind it.',
      content: <MoneyOverviewPanel dashboard={dashboard} />,
    },
    {
      value: 'accounts',
      label: 'Accounts',
      description:
        'Every account/entity card shows freshness, confidence, and the exact gaps Jenny still sees.',
      badge:
        dashboard.overview.needsRefreshCount > 0
          ? String(dashboard.overview.needsRefreshCount)
          : undefined,
      content: (
        <MoneyAccountsPanel
          accounts={dashboard.accounts}
          documents={documentItems}
        />
      ),
    },
    {
      value: 'inbox',
      label: 'Inbox',
      description:
        'One ranked list of stale accounts, missing evidence, and focused clarifications.',
      badge:
        dashboard.overview.inboxCount > 0
          ? String(dashboard.overview.inboxCount)
          : undefined,
      content: (
        <MoneyInboxPanel
          inbox={dashboard.inbox}
          questions={dashboard.questions}
        />
      ),
    },
    {
      value: 'intake',
      label: 'Intake',
      description:
        'Use the single evidence inbox for uploads, then inspect what Jenny understood.',
      badge: trackedDocuments > 0 ? String(trackedDocuments) : undefined,
      content: intakeContent,
    },
    {
      value: 'planning',
      label: 'Planning',
      description:
        'Keep profile assumptions, goals, and planning context available without crowding the default view.',
      badge:
        dashboard.questions.length > 0
          ? String(dashboard.questions.length)
          : undefined,
      content: (
        <div className="space-y-6">
          <HouseholdProfileCard
            profile={dashboard.profile}
            resolvedValues={dashboard.resolvedValues}
          />
          <HouseholdPlanningPanels dashboard={dashboard} />
        </div>
      ),
    },
  ]

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        eyebrow="Household Finance"
        title="Money System"
        description="One compact view of accounts, cash flow, evidence freshness, and what Jenny still needs."
      />

      <SectionCard
        variant="surface"
        title="Next Up"
        description="The top priority comes from the same inbox that drives the rest of the page."
        actions={
          primaryInboxItem?.actionHref ? (
            <Link
              href={primaryInboxItem.actionHref}
              className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/15"
            >
              {primaryInboxItem.actionLabel}
            </Link>
          ) : undefined
        }
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xl font-semibold tracking-tight text-text">
              {primaryInboxItem?.title ?? dashboard.overview.nextBestAction}
            </p>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-muted">
              {primaryInboxItem?.detail ??
                'Jenny is keeping the overview, account cards, and inbox aligned to the same evidence-backed account model.'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-text-muted">
            <span className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1.5">
              {dashboard.overview.visibilityLabel}
            </span>
            <span className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1.5">
              {dashboard.overview.visibilityScore}/100 visibility
            </span>
            <span className="rounded-full border border-border/40 bg-surface-muted/20 px-3 py-1.5">
              Updated {formatRelativeTime(dashboard.generatedAt)}
            </span>
          </div>
        </div>
      </SectionCard>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
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
        defaultValue="overview"
        ariaLabel="Money workspace sections"
        tabs={tabs}
      />
    </PageContainer>
  )
}
