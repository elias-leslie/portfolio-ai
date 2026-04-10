'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import type {
  HouseholdDocument,
  HouseholdDocumentRequirement,
  HouseholdTransactionDateIssue,
  ImportCenter,
} from '@/lib/api/household'
import { EvidenceUploadComposer } from './EvidenceUploadComposer'
import { ImportCenterSidebar } from './ImportCenterSidebar'

export function HouseholdDocumentCenter({
  documents,
  importCenter,
  documentRequirements = [],
  dateQualityIssues = [],
  focusedReview = false,
}: {
  documents: HouseholdDocument[]
  importCenter?: ImportCenter
  documentRequirements?: HouseholdDocumentRequirement[]
  dateQualityIssues?: HouseholdTransactionDateIssue[]
  focusedReview?: boolean
}) {
  return (
    <SectionCard
      variant="surface"
      title="Evidence Intake"
      description="Add anything once. Jenny should determine what it is, what matters, and whether it belongs in cash-flow, portfolio, planning, or reference context."
    >
      <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <div id="add-evidence-upload">
          <EvidenceUploadComposer
            title="Add anything"
            description="Statements, screenshots, exports, payroll docs, bills, and receipts all go through the same intake path."
          />
        </div>

        <ImportCenterSidebar
          documents={documents}
          importCenter={importCenter}
          documentRequirements={documentRequirements}
          dateQualityIssues={dateQualityIssues}
          focusedReview={focusedReview}
        />
      </div>
    </SectionCard>
  )
}
