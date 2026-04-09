import { Badge } from '@/components/ui/badge'
import type {
  HouseholdDocument,
  HouseholdDocumentRequirement,
  ImportCenter,
} from '@/lib/api/household'
import { formatEnumLabel } from '@/lib/formatters'
import { DocumentCard } from './DocumentCard'

export function ImportCenterSidebar({
  documents,
  importCenter,
  documentRequirements,
}: {
  documents: HouseholdDocument[]
  importCenter?: ImportCenter
  documentRequirements: HouseholdDocumentRequirement[]
}) {
  return (
    <div className="space-y-3">
      {importCenter ? <IntakeSummaryCard importCenter={importCenter} /> : null}
      {documentRequirements.length > 0 ? (
        <DocumentRequirementsCard requirements={documentRequirements} />
      ) : null}
      {documents.length === 0 ? (
        <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-5 text-sm text-text-muted">
          No evidence yet. Start with whatever best reflects your finances right
          now: statements, brokerage screenshots, exports, payroll docs, bills,
          or receipts.
        </div>
      ) : (
        documents.map((document) => (
          <DocumentCard key={document.id} document={document} />
        ))
      )}
    </div>
  )
}

function IntakeSummaryCard({ importCenter }: { importCenter: ImportCenter }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <p className="text-sm font-semibold text-text">Recent intake status</p>
      <p className="mt-1 text-sm text-text-muted">
        Jenny keeps using the same inbox for raw uploads and parsed financial
        evidence.
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-border/40 bg-surface/60 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            Documents
          </p>
          <p className="mt-2 text-2xl font-semibold text-text">
            {importCenter.trackedDocuments}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            {importCenter.parsedDocuments} parsed so far
          </p>
        </div>
        <div className="rounded-2xl border border-border/40 bg-surface/60 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            Likely next
          </p>
          {importCenter.suggestedFirstUploads.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {importCenter.suggestedFirstUploads.slice(0, 3).map((item) => (
                <Badge key={item} variant="outline">
                  {item}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-text-muted">
              Jenny will suggest the next-best upload only when she sees a real
              coverage gap.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function DocumentRequirementsCard({
  requirements,
}: {
  requirements: HouseholdDocumentRequirement[]
}) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <p className="text-sm font-semibold text-text">Known gaps Jenny sees</p>
      <div className="mt-3 space-y-3">
        {requirements.slice(0, 6).map((requirement) => (
          <div key={requirement.id}>
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-text">
                {requirement.label}
              </p>
              <Badge
                variant={
                  requirement.status === 'received' ? 'success' : 'outline'
                }
              >
                {formatEnumLabel(requirement.status)}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-text-muted">
              {requirement.rationale ??
                'Jenny is waiting on this planning document.'}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
