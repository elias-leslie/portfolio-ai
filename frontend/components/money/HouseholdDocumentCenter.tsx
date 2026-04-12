'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import type {
  HouseholdDocument,
  HouseholdDocumentRequirement,
  HouseholdInboxItem,
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
  moneyInbox = [],
  focusedReview = false,
}: {
  documents: HouseholdDocument[]
  importCenter?: ImportCenter
  documentRequirements?: HouseholdDocumentRequirement[]
  dateQualityIssues?: HouseholdTransactionDateIssue[]
  moneyInbox?: HouseholdInboxItem[]
  focusedReview?: boolean
}) {
  return (
    <SectionCard
      variant="surface"
      title="Evidence Intake"
      description="Add money evidence once. Jenny should determine what it is, which account it affects, and whether it updates balances, transactions, recurring spend, or price tracking."
    >
      <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <div id="add-evidence-upload">
          <EvidenceUploadComposer
            title="Add anything"
            description="Statements, screenshots, exports, copied account text, payroll docs, bills, and receipts all go through the same intake path."
          />
        </div>

        <ImportCenterSidebar
          documents={documents}
          importCenter={importCenter}
          documentRequirements={documentRequirements}
          dateQualityIssues={dateQualityIssues}
          moneyInbox={moneyInbox}
          focusedReview={focusedReview}
        />
      </div>
    </SectionCard>
  )
}
