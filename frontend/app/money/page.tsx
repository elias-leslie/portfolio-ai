'use client'

import { ArrowRight, FileUp, Loader2, Search, ThumbsUp } from 'lucide-react'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { HouseholdDocumentCenter } from '@/components/money/HouseholdDocumentCenter'
import { HouseholdOperationsPanel } from '@/components/money/HouseholdOperationsPanel'
import { HouseholdOverviewGrid } from '@/components/money/HouseholdOverviewGrid'
import { HouseholdPlanningPanels } from '@/components/money/HouseholdPlanningPanels'
import { HouseholdProfileCard } from '@/components/money/HouseholdProfileCard'
import { HouseholdReportsPanel } from '@/components/money/HouseholdReportsPanel'
import { JennyChatPanel } from '@/components/money/JennyChatPanel'
import { JennyQuestionInbox } from '@/components/money/JennyQuestionInbox'
import { JennyMoneyBoard } from '@/components/money/JennyMoneyBoard'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import type { WorkspaceTab } from '@/components/shared/WorkspaceTabs'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { useHouseholdDashboard, useHouseholdDocuments } from '@/lib/hooks/useHousehold'
import { formatRelativeTime } from '@/lib/utils'

type OnboardingStage = 1 | 2 | 3 | 4

function getOnboardingStage(
  dashboard: HouseholdFinanceDashboard,
  docCount: number,
): OnboardingStage {
  const executive = dashboard.reports?.executive as
    | HouseholdFinanceDashboard['reports']['executive']
    | undefined
  if (docCount === 0 && !executive) return 1
  if (docCount > 0 && !executive?.averageMonthlySpend) return 2
  const criticalHighNeeds = dashboard.jennyNeeds?.filter(
    (n) =>
      n.status === 'unsatisfied' &&
      (n.priority === 'critical' || n.priority === 'high'),
  )
  if (!criticalHighNeeds || criticalHighNeeds.length === 0) return 4
  const hasConfirmed = dashboard.resolvedValues?.some(
    (v) => v.status === 'confirmed',
  )
  if (hasConfirmed) return 4
  return 3
}

function LoadingState() {
  return (
    <div className="flex min-h-96 items-center justify-center rounded-3xl border border-border/40 bg-surface-muted/20">
      <div className="flex items-center gap-3 text-sm font-medium text-text-muted">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        Building your household finance workspace...
      </div>
    </div>
  )
}

const onboardingSteps = [
  {
    icon: FileUp,
    title: 'Upload',
    detail: 'Drop 1-2 months of bank or credit card statements.',
  },
  {
    icon: Search,
    title: 'Jenny analyzes',
    detail:
      'She reads every line, categorizes spending, and finds patterns.',
  },
  {
    icon: ThumbsUp,
    title: 'You confirm',
    detail: 'Review what Jenny found, answer a few questions, and go.',
  },
]

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
          description="One place for budgeting, saving, statement intake, and retirement preparedness."
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
          description="One place for budgeting, saving, statement intake, and retirement preparedness."
        />
        <LoadErrorState
          title="Failed to load the household finance workspace."
          detail="Retry to refresh the household dashboard before working through questions, reports, and planning."
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

  const docCount =
    documents?.items.length ?? dashboard.importCenter.trackedDocuments
  const stage = getOnboardingStage(dashboard, docCount)
  const unsatisfiedNeedCount = dashboard.jennyNeeds.filter(
    (n) => n.status === 'unsatisfied',
  ).length

  // Stage 1: No data at all — focused onboarding with intake UI only
  if (stage === 1) {
    return (
      <PageContainer className="space-y-10 py-10">
        <PageHeader
          eyebrow="Household Finance"
          title="Let Jenny see your finances"
          description="Upload 1-2 months of bank or credit card statements. Jenny will analyze your cash flow, categorize spending, and build your financial picture automatically."
        />

        <div className="grid gap-4 md:grid-cols-3">
          {onboardingSteps.map((step, index) => (
            <SectionCard
              key={step.title}
              variant="surface"
              className="overflow-hidden"
              contentClassName="space-y-3"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                  {index + 1}
                </div>
                <step.icon className="h-5 w-5 text-primary" />
                <p className="text-sm font-semibold text-text">
                  {step.title}
                </p>
              </div>
              <p className="text-sm leading-6 text-text-muted">
                {step.detail}
              </p>
            </SectionCard>
          ))}
        </div>

        {documentsError ? (
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
            documents={documents?.items ?? []}
            importCenter={dashboard.importCenter}
          />
        )}
      </PageContainer>
    )
  }

  // Stage 2: Documents uploaded but not yet processed — intake + status
  if (stage === 2) {
    return (
      <PageContainer className="space-y-10 py-10">
        <PageHeader
          eyebrow="Household Finance"
          title="Money System"
          description="Jenny is getting to know your finances. More tools unlock as she processes your statements."
        />

        <div className="rounded-2xl border border-primary/30 bg-primary/5 px-5 py-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <div>
              <p className="text-sm font-semibold text-text">
                Jenny is analyzing your statements...
              </p>
              <p className="mt-1 text-sm text-text-muted">
                She is reading transactions, categorizing spending, and building
                your financial picture. Analysis and planning tools will unlock
                once processing is complete.
              </p>
            </div>
          </div>
        </div>

        <WorkspaceTabs
          defaultValue="intake"
          ariaLabel="Money workspace sections"
          tabs={[
            {
              value: 'intake',
              label: 'Intake',
              description:
                'Upload and audit source documents. Add more statements to give Jenny a fuller picture.',
              badge: docCount > 0 ? String(docCount) : undefined,
              content: documentsError ? (
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
                  documents={documents?.items ?? []}
                  importCenter={dashboard.importCenter}
                />
              ),
            },
            {
              value: 'operate',
              label: 'Operate',
              description:
                'Handle what Jenny needs while she processes your documents.',
              badge:
                unsatisfiedNeedCount > 0
                  ? String(unsatisfiedNeedCount)
                  : undefined,
              content: (
                <HouseholdOperationsPanel dashboard={dashboard} />
              ),
            },
          ]}
        />
      </PageContainer>
    )
  }

  // Stage 3 and 4: Build the full tab set, gating Operate to stage 4
  const intakeTab: WorkspaceTab = {
    value: 'intake',
    label: 'Intake',
    description:
      'Upload and audit source documents without forcing the rest of the page to grow.',
    badge: docCount > 0 ? String(docCount) : undefined,
    content: documentsError ? (
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
        documents={documents?.items ?? []}
        importCenter={dashboard.importCenter}
        documentRequirements={dashboard.planning?.documentRequirements ?? []}
      />
    ),
  }

  const analysisTab: WorkspaceTab = {
    value: 'analysis',
    label: 'Analysis',
    description:
      "Review the transaction reports and Jenny\u2019s synthesized money brief together.",
    content: (
      <div className="space-y-6">
        <HouseholdReportsPanel dashboard={dashboard} />
        <JennyMoneyBoard dashboard={dashboard} />
      </div>
    ),
  }

  const planningTab: WorkspaceTab = {
    value: 'planning',
    label: 'Planning',
    description:
      'Keep profile assumptions and long-range planning in one place.',
    badge:
      dashboard.resolvedValues.length > 0
        ? String(dashboard.resolvedValues.length)
        : undefined,
    content: (
      <div className="space-y-6">
        {stage < 4 && dashboard.questions.length > 0 ? (
          <JennyQuestionInbox
            questions={dashboard.questions}
            title="Questions Blocking Jenny"
            description="Before Operate is unlocked, answer Jenny here so she can finish building the household system."
          />
        ) : null}
        {stage < 4 ? <JennyChatPanel title="Talk to Jenny" /> : null}
        <HouseholdProfileCard
          profile={dashboard.profile}
          resolvedValues={dashboard.resolvedValues}
        />
        <HouseholdPlanningPanels dashboard={dashboard} />
      </div>
    ),
  }

  const operateTab: WorkspaceTab = {
    value: 'operate',
    label: 'Operate',
    description:
      'Handle what Jenny needs, review categories, bills, and budget pacing.',
    badge: unsatisfiedNeedCount > 0 ? String(unsatisfiedNeedCount) : undefined,
    content: <HouseholdOperationsPanel dashboard={dashboard} />,
  }

  const tabs: WorkspaceTab[] =
    stage === 4
      ? [operateTab, analysisTab, planningTab, intakeTab]
      : [analysisTab, planningTab, intakeTab]

  const defaultTab = stage === 4 ? 'operate' : 'analysis'

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        eyebrow="Household Finance"
        title="Money System"
        description="Budgeting, savings, retirement planning, and document intake in one shared workspace for you and Jenny."
      />

      <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-sm text-text-muted">
        Updated {formatRelativeTime(dashboard.generatedAt)}
        {' \u00b7 '}
        {unsatisfiedNeedCount} need
        {unsatisfiedNeedCount === 1 ? '' : 's'}
        {' \u00b7 '}
        {docCount} document
        {docCount === 1 ? '' : 's'}
        {' \u00b7 '}
        Next best action: {dashboard.overview.nextBestAction}
      </div>

      {stage === 3 ? (
        <div className="flex items-start gap-3 rounded-2xl border border-primary/30 bg-primary/5 px-5 py-4">
          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <div>
            <p className="text-sm font-semibold text-text">
              Here is what Jenny found
            </p>
            <p className="mt-1 text-sm text-text-muted">
              Your reports and analysis are ready. Review the findings, confirm
              key assumptions in Planning, and Jenny will unlock your full
              operating workspace.
            </p>
          </div>
        </div>
      ) : null}

      <HouseholdOverviewGrid dashboard={dashboard} stage={stage} />
      <WorkspaceTabs
        defaultValue={defaultTab}
        ariaLabel="Money workspace sections"
        tabs={tabs}
      />
    </PageContainer>
  )
}
