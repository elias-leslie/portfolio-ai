'use client'

import { useEffect, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import type {
  HouseholdTransactionDateIssue,
  ImportCenter,
} from '@/lib/api/household'
import { EvidenceUploadComposer } from './EvidenceUploadComposer'
import { ImportCenterSidebar } from './ImportCenterSidebar'

export function HouseholdDocumentCenter({
  importCenter,
  dateQualityIssues = [],
  focusedReview = false,
}: {
  importCenter?: ImportCenter
  dateQualityIssues?: HouseholdTransactionDateIssue[]
  focusedReview?: boolean
}) {
  const [uploadOpen, setUploadOpen] = useState(false)
  useEffect(() => {
    const showUpload = () => {
      if (window.location.hash === '#add-evidence-upload') setUploadOpen(true)
    }
    showUpload()
    window.addEventListener('hashchange', showUpload)
    window.addEventListener('locationchange', showUpload)
    return () => {
      window.removeEventListener('hashchange', showUpload)
      window.removeEventListener('locationchange', showUpload)
    }
  }, [])
  return (
    <SectionCard
      variant="surface"
      title="Evidence Intake"
      description="Resolve pending decisions using the original evidence and exact proposed changes."
    >
      <div className="space-y-6">
        <ImportCenterSidebar
          importCenter={importCenter}
          dateQualityIssues={dateQualityIssues}
          focusedReview={focusedReview}
        />
        <details
          id="add-evidence-upload"
          open={uploadOpen}
          onToggle={(event) => setUploadOpen(event.currentTarget.open)}
          className="scroll-mt-64 rounded-xl border p-4 md:scroll-mt-48"
        >
          <summary className="cursor-pointer font-medium">
            Add anything · Upload evidence
          </summary>
          <div className="mt-4">
            <EvidenceUploadComposer
              title="Add evidence"
              description="Statements, screenshots, exports, account text, bills, and receipts."
            />
          </div>
        </details>
      </div>
    </SectionCard>
  )
}
