'use client'

import Link from 'next/link'
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
import { Button } from '@/components/ui/button'
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

function getOnboardingStageLabel(stage: OnboardingStage): string {
  switch (stage) {
    case 1:
      return 'Intake setup'
    case 2:
      return 'Document processing'
    case 3:
      return 'Confirm assumptions'
    case 4:
      return 'Operate'
  }
}

function getPrimaryNeedAction(dashboard: HouseholdFinanceDashboard): {
  href: string
  label: string
} | null {
  const actionableNeed = dashboard.jennyNeeds.find(
    (need) => need.status === 'unsatisfied' && Boolean(need.actionHref),
  )

  if (!actionableNeed?.actionHref) {
    return null
  }

  return {
    href: actionableNeed.actionHref,
    label: actionableNeed.title,
  }
}

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
  const stageLabel = getOnboardingStageLabel(stage)
  const unsatisfiedNeedCount = dashboard.jennyNeeds.filter(
    (n) => n.status === 'unsatisfied',
  ).length
  const openQuestionCount = dashboard.questions.filter(
    (question) => !question.answeredAt,
  ).length
  const evidenceMonths = dashboard.reports.executive.coverageMonths
  const primaryNeedAction = getPrimaryNeedAction(dashboard)

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
    badge: evidenceMonths > 0 ? `${evidenceMonths} mo` : undefined,
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
      openQuestionCount > 0
        ? String(openQuestionCount)
        : dashboard.resolvedValues.length > 0
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

      <div className="rounded-2xl border border-border/30 border-l-2 border-l-primary/40 bg-surface/40 px-5 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-text-muted">
              <span className="rounded-full border border-border/50 bg-background/70 px-2.5 py-1 tracking-[0.18em]">
                Stage {stage} of 4
              </span>
              <span>{stageLabel}</span>
            </div>
            <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
              <h2 className="text-2xl font-semibold tracking-tight text-text">
                {dashboard.overview.visibilityLabel}
              </h2>
              <p className="text-sm text-text-muted">
                {dashboard.overview.visibilityScore}/100 visibility score
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-sm">
              <span className="rounded-full bg-background/80 px-3 py-1.5 text-text">
                {unsatisfiedNeedCount} need{unsatisfiedNeedCount === 1 ? '' : 's'}
              </span>
              <span className="rounded-full bg-background/80 px-3 py-1.5 text-text">
                {openQuestionCount} open question{openQuestionCount === 1 ? '' : 's'}
              </span>
              <span className="rounded-full bg-background/80 px-3 py-1.5 text-text">
                {dashboard.importCenter.parsedDocuments}/{docCount} documents parsed
              </span>
              {evidenceMonths > 0 ? (
                <span className="rounded-full bg-background/80 px-3 py-1.5 text-text">
                  {evidenceMonths} month{evidenceMonths === 1 ? '' : 's'} of evidence
                </span>
              ) : null}
              <span className="rounded-full bg-background/80 px-3 py-1.5 text-text">
                Updated {formatRelativeTime(dashboard.generatedAt)}
              </span>
            </div>
          </div>
          <div className="flex w-full flex-col gap-2 lg:w-auto lg:max-w-sm lg:items-end">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-text-muted">
              Next best action
            </p>
            <p className="text-sm text-text lg:text-right">
              {dashboard.overview.nextBestAction}
            </p>
            {primaryNeedAction ? (
              <Button asChild size="sm" className="w-full lg:w-auto">
                <Link href={primaryNeedAction.href}>{primaryNeedAction.label}</Link>
              </Button>
            ) : null}
          </div>
        </div>
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
