import type {
  HouseholdDocument,
  HouseholdDocumentRequirement,
  HouseholdEvidenceAccount,
  ImportCenter,
} from '@/lib/api/household'
import { Badge } from '@/components/ui/badge'
import { formatCurrencyWhole, formatEnumLabel } from '@/lib/formatters'
import { formatDate } from '@/lib/utils'
import { DocumentCard } from './DocumentCard'

export function ImportCenterSidebar({
  documents,
  importCenter,
  documentRequirements,
  evidenceAccounts = [],
}: {
  documents: HouseholdDocument[]
  importCenter?: ImportCenter
  documentRequirements: HouseholdDocumentRequirement[]
  evidenceAccounts?: HouseholdEvidenceAccount[]
}) {
  return (
    <div className="space-y-3">
      {importCenter ? <IntakeCoverageCards importCenter={importCenter} /> : null}
      {evidenceAccounts.length > 0 ? <EvidenceAccountsCard accounts={evidenceAccounts} /> : null}
      {importCenter?.automations.length ? <AutomationsCard automations={importCenter.automations} /> : null}
      {importCenter?.supportedDocuments.length ? <SupportedDocumentsCard supportedDocuments={importCenter.supportedDocuments} /> : null}
      {documentRequirements.length > 0 ? <DocumentRequirementsCard requirements={documentRequirements} /> : null}
      {documents.length === 0 ? (
        <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-5 text-sm text-text-muted">
          No evidence yet. Start with whatever best reflects your finances right now: statements, brokerage screenshots, exports, payroll docs, bills, or receipts.
        </div>
      ) : (
        documents.map((document) => <DocumentCard key={document.id} document={document} />)
      )}
    </div>
  )
}

function EvidenceAccountsCard({ accounts }: { accounts: HouseholdEvidenceAccount[] }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <p className="text-sm font-semibold text-text">Accounts Jenny derived</p>
      <p className="mt-1 text-sm text-text-muted">
        Evidence-derived account snapshots that can immediately inform the money system.
      </p>
      <div className="mt-3 space-y-3">
        {accounts.slice(0, 5).map((account) => {
          const title =
            account.accountName ??
            account.institutionName ??
            account.accountMask ??
            formatEnumLabel(account.accountType)
          const total =
            account.balance ??
            ((account.holdingsValue ?? 0) + (account.cashBalance ?? 0) || null)
          return (
            <div key={account.id} className="rounded-2xl border border-border/40 bg-surface/60 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-text">{title}</p>
                  <p className="mt-1 text-xs text-text-muted">
                    {[
                      account.institutionName,
                      account.accountMask ? `...${account.accountMask}` : null,
                      formatEnumLabel(account.assetGroup),
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                  {account.asOfDate ? (
                    <p className="mt-1 text-xs text-text-muted">
                      As of {formatDate(account.asOfDate, true)}
                    </p>
                  ) : null}
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-text">
                    {formatCurrencyWhole(total)}
                  </p>
                  {account.confidence != null ? (
                    <p className="mt-1 text-xs text-text-muted">
                      {Math.round(account.confidence * 100)}% confidence
                    </p>
                  ) : null}
                </div>
              </div>
            </div>
          )
        })}
      </div>
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
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Likely next evidence</p>
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
      <p className="text-sm font-semibold text-text">Examples Jenny can interpret</p>
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
      <p className="text-sm font-semibold text-text">Known gaps Jenny sees</p>
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
