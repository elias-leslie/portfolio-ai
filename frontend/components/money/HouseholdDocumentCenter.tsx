'use client'

import { useState } from 'react'
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
  const [dateQualityRepairIssue, setDateQualityRepairIssue] =
    useState<HouseholdTransactionDateIssue | null>(null)

  const selectDateQualityRepairIssue = (
    issue: HouseholdTransactionDateIssue,
  ) => {
    setDateQualityRepairIssue(issue)
    requestAnimationFrame(() => {
      document
        .getElementById('add-evidence-upload')
        ?.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
    })
  }

  return (
    <SectionCard
      variant="surface"
      title="Evidence Intake"
      description="Add money evidence once. Jenny should determine what it is, which account it affects, and whether it updates balances, transactions, recurring spend, or price tracking."
    >
      <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <div id="add-evidence-upload" className="scroll-mt-40">
          <EvidenceUploadComposer
            title="Add anything"
            description="Statements, screenshots, exports, copied account text, bills, and receipts all go through the same intake path."
            dateQualityRepairIssue={dateQualityRepairIssue}
            onClearDateQualityRepair={() => setDateQualityRepairIssue(null)}
          />
        </div>

        <ImportCenterSidebar
          documents={documents}
          importCenter={importCenter}
          documentRequirements={documentRequirements}
          dateQualityIssues={dateQualityIssues}
          moneyInbox={moneyInbox}
          focusedReview={focusedReview}
          onRepairDateIssue={selectDateQualityRepairIssue}
        />
      </div>
    </SectionCard>
  )
}
