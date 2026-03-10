'use client'

import { Loader2 } from 'lucide-react'
import { HouseholdDocumentCenter } from '@/components/money/HouseholdDocumentCenter'
import { HouseholdOperationsPanel } from '@/components/money/HouseholdOperationsPanel'
import { HouseholdOverviewGrid } from '@/components/money/HouseholdOverviewGrid'
import { HouseholdPlanningPanels } from '@/components/money/HouseholdPlanningPanels'
import { HouseholdProfileCard } from '@/components/money/HouseholdProfileCard'
import { HouseholdReportsPanel } from '@/components/money/HouseholdReportsPanel'
import { JennyMoneyBoard } from '@/components/money/JennyMoneyBoard'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { WorkspaceTabs } from '@/components/shared/WorkspaceTabs'
import { useHouseholdDashboard, useHouseholdDocuments } from '@/lib/hooks/useHousehold'

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

export default function MoneyPage() {
  const { data: dashboard, isLoading, error } = useHouseholdDashboard()
  const { data: documents } = useHouseholdDocuments()

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
        <div className="rounded-3xl border border-border/40 bg-surface-muted/20 p-8 text-sm text-text-muted">
          Failed to load the household finance workspace.
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        eyebrow="Household Finance"
        title="Money System"
        description="Budgeting, savings, retirement planning, and document intake in one shared workspace for you and Jenny."
      />

      <HouseholdOverviewGrid dashboard={dashboard} />
      <WorkspaceTabs
        defaultValue="operate"
        tabs={[
          {
            value: 'operate',
            label: 'Operate',
            description: 'Handle active questions, categorization review, bills, and budget pacing first.',
            content: <HouseholdOperationsPanel dashboard={dashboard} />,
          },
          {
            value: 'analysis',
            label: 'Analysis',
            description: 'Review the transaction reports and Jenny’s synthesized money brief together.',
            content: (
              <div className="space-y-6">
                <HouseholdReportsPanel dashboard={dashboard} />
                <JennyMoneyBoard dashboard={dashboard} />
              </div>
            ),
          },
          {
            value: 'planning',
            label: 'Planning',
            description: 'Keep profile assumptions and long-range planning in one place.',
            content: (
              <div className="space-y-6">
                <HouseholdProfileCard
                  profile={dashboard.profile}
                  resolvedValues={dashboard.resolvedValues}
                  questions={dashboard.questions}
                />
                <HouseholdPlanningPanels dashboard={dashboard} />
              </div>
            ),
          },
          {
            value: 'intake',
            label: 'Intake',
            description: 'Upload and audit source documents without forcing the rest of the page to grow.',
            content: <HouseholdDocumentCenter documents={documents?.items ?? []} />,
          },
        ]}
      />
    </PageContainer>
  )
}
