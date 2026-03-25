import type {
  HouseholdDocument,
  HouseholdDocumentRequirement,
  ImportCenter,
} from '@/lib/api/household'
import { Badge } from '@/components/ui/badge'
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
      {importCenter ? <IntakeCoverageCards importCenter={importCenter} /> : null}
      {importCenter?.automations.length ? <AutomationsCard automations={importCenter.automations} /> : null}
      {importCenter?.supportedDocuments.length ? <SupportedDocumentsCard supportedDocuments={importCenter.supportedDocuments} /> : null}
      {documentRequirements.length > 0 ? <DocumentRequirementsCard requirements={documentRequirements} /> : null}
      {documents.length === 0 ? (
        <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-5 text-sm text-text-muted">
          No documents yet. Start with recent bank and credit-card statements so Jenny can see the real household cash flow.
        </div>
      ) : (
        documents.map((document) => <DocumentCard key={document.id} document={document} />)
      )}
    </div>
  )
}

function IntakeCoverageCards({ importCenter }: { importCenter: ImportCenter }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Intake coverage</p>
        <p className="mt-2 text-2xl font-semibold text-text">{importCenter.trackedDocuments}</p>
        <p className="mt-1 text-sm text-text-muted">{importCenter.parsedDocuments} parsed so far</p>
      </div>
      <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Next best uploads</p>
        {importCenter.suggestedFirstUploads.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {importCenter.suggestedFirstUploads.map((item) => (
              <Badge key={item} variant="outline">{item}</Badge>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-text-muted">
            Intake guidance appears after Jenny sees gaps in the household record.
          </p>
        )}
      </div>
    </div>
  )
}

function AutomationsCard({ automations }: { automations: string[] }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <p className="text-sm font-semibold text-text">What Jenny will automate</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {automations.map((automation) => (
          <Badge key={automation} variant="secondary">{automation}</Badge>
        ))}
      </div>
    </div>
  )
}

function SupportedDocumentsCard({ supportedDocuments }: { supportedDocuments: ImportCenter['supportedDocuments'] }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <p className="text-sm font-semibold text-text">Supported document types</p>
      <div className="mt-3 space-y-3">
        {supportedDocuments.map((documentType) => (
          <div key={documentType.label}>
            <p className="text-sm font-medium text-text">{documentType.label}</p>
            <p className="mt-1 text-sm text-text-muted">Formats: {documentType.formats.join(', ')}</p>
            <p className="mt-1 text-xs text-text-muted">Extracts: {documentType.extracts.join(', ')}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function DocumentRequirementsCard({ requirements }: { requirements: HouseholdDocumentRequirement[] }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <p className="text-sm font-semibold text-text">Planning document placeholders</p>
      <div className="mt-3 space-y-3">
        {requirements.slice(0, 6).map((requirement) => (
          <div key={requirement.id}>
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-text">{requirement.label}</p>
              <Badge variant={requirement.status === 'received' ? 'success' : 'outline'}>
                {formatEnumLabel(requirement.status)}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-text-muted">
              {requirement.rationale ?? 'Jenny is waiting on this planning document.'}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
