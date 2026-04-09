'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import type {
  HouseholdDocument,
  HouseholdDocumentRequirement,
  ImportCenter,
} from '@/lib/api/household'
import { EvidenceUploadComposer } from './EvidenceUploadComposer'
import { ImportCenterSidebar } from './ImportCenterSidebar'

export function HouseholdDocumentCenter({
  documents,
  importCenter,
  documentRequirements = [],
}: {
  documents: HouseholdDocument[]
  importCenter?: ImportCenter
  documentRequirements?: HouseholdDocumentRequirement[]
}) {
  return (
    <SectionCard
      variant="surface"
      title="Evidence Intake"
      description="Add anything once. Jenny should determine what it is, what matters, and whether it belongs in cash-flow, portfolio, planning, or reference context."
    >
      <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <EvidenceUploadComposer
          title="Add anything"
          description="Statements, screenshots, exports, payroll docs, bills, and receipts all go through the same intake path."
        />

        <ImportCenterSidebar
          documents={documents}
          importCenter={importCenter}
          documentRequirements={documentRequirements}
        />
      </div>
    </SectionCard>
  )
}
