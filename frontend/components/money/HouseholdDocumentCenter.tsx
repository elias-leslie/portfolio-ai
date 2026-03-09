'use client'

import { useRef, useState } from 'react'
import type { HouseholdDocument } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUploadHouseholdDocument } from '@/lib/hooks/useHousehold'
import { formatFileSize } from './formatters'

const SOURCE_OPTIONS = [
  { value: 'bank', label: 'Bank' },
  { value: 'credit_card', label: 'Credit card' },
  { value: 'brokerage', label: 'Brokerage' },
  { value: 'retirement', label: 'Retirement' },
  { value: 'receipt', label: 'Receipt' },
  { value: 'billing', label: 'Invoice or bill' },
]

const DOCUMENT_OPTIONS = [
  { value: 'statement', label: 'Statement' },
  { value: 'brokerage_statement', label: 'Brokerage statement' },
  { value: 'retirement_statement', label: 'Retirement statement' },
  { value: 'receipt', label: 'Receipt' },
  { value: 'invoice', label: 'Invoice' },
]

export function HouseholdDocumentCenter({
  documents,
}: {
  documents: HouseholdDocument[]
}) {
  const upload = useUploadHouseholdDocument()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [sourceType, setSourceType] = useState('')
  const [documentType, setDocumentType] = useState('')
  const [accountLabel, setAccountLabel] = useState('')

  const handleUpload = () => {
    if (!file) {
      return
    }

    upload.mutate(
      {
        file,
        sourceType: sourceType || undefined,
        documentType: documentType || undefined,
        accountLabel: accountLabel.trim() || undefined,
      },
      {
        onSuccess: () => {
          setFile(null)
          setSourceType('')
          setDocumentType('')
          setAccountLabel('')
          if (inputRef.current) {
            inputRef.current.value = ''
          }
        },
      },
    )
  }

  return (
    <SectionCard
      variant="surface"
      title="Document Intake"
      description="Upload statements, receipts, and invoices here. Jenny uses this queue as the raw material for budgeting and savings intelligence."
    >
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-2xl border border-dashed border-primary/30 bg-primary/5 p-5">
          <p className="text-sm font-semibold text-text">Stage a document</p>
          <div className="mt-4 space-y-4">
            <div>
              <Label htmlFor="document-file">File</Label>
              <Input
                id="document-file"
                ref={inputRef}
                type="file"
                accept=".pdf,.csv,.ofx,.qfx,.png,.jpg,.jpeg,.heic"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="source-type">Source type</Label>
                <Select value={sourceType} onValueChange={setSourceType}>
                  <SelectTrigger id="source-type" className="mt-2">
                    <SelectValue placeholder="Auto-detect if blank" />
                  </SelectTrigger>
                  <SelectContent>
                    {SOURCE_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="document-type">Document type</Label>
                <Select value={documentType} onValueChange={setDocumentType}>
                  <SelectTrigger id="document-type" className="mt-2">
                    <SelectValue placeholder="Auto-detect if blank" />
                  </SelectTrigger>
                  <SelectContent>
                    {DOCUMENT_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label htmlFor="account-label">Account label</Label>
              <Input
                id="account-label"
                value={accountLabel}
                onChange={(event) => setAccountLabel(event.target.value)}
                placeholder="Amex Gold, Joint Checking, Fidelity Roth IRA..."
              />
            </div>
            <Button onClick={handleUpload} disabled={!file || upload.isPending}>
              {upload.isPending ? 'Uploading...' : 'Stage Document'}
            </Button>
          </div>
        </div>

        <div className="space-y-3">
          {documents.length === 0 ? (
            <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-5 text-sm text-text-muted">
              No documents yet. Start with recent bank and credit-card statements so Jenny can see the real household cash flow.
            </div>
          ) : (
            documents.map((document) => (
              <div
                key={document.id}
                className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">{document.filename}</p>
                    <p className="mt-1 text-sm text-text-muted">
                      {document.sourceType.replaceAll('_', ' ')} ·{' '}
                      {document.documentType.replaceAll('_', ' ')}
                    </p>
                    {document.accountLabel ? (
                      <p className="mt-1 text-sm text-text-muted">{document.accountLabel}</p>
                    ) : null}
                  </div>
                  <div className="text-right text-xs text-text-muted">
                    <p>{document.status.replaceAll('_', ' ')}</p>
                    <p className="mt-1">{formatFileSize(document.fileSizeBytes)}</p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </SectionCard>
  )
}
