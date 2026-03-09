'use client'

import { useRef, useState } from 'react'
import type { ClipboardEvent, DragEvent, KeyboardEvent } from 'react'
import type { HouseholdDocument } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useUploadHouseholdDocument } from '@/lib/hooks/useHousehold'
import { formatFileSize } from './formatters'

export function HouseholdDocumentCenter({
  documents,
}: {
  documents: HouseholdDocument[]
}) {
  const upload = useUploadHouseholdDocument()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [isDragActive, setIsDragActive] = useState(false)

  const resetComposer = () => {
    setFile(null)
    setIsDragActive(false)
    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }

  const pickFirstFile = (files: FileList | File[] | null | undefined): File | null => {
    if (!files || files.length === 0) {
      return null
    }
    return files[0] ?? null
  }

  const stageIncomingFile = (incoming: File | null) => {
    if (!incoming) {
      return
    }
    setFile(incoming)
  }

  const handlePaste = (event: ClipboardEvent<HTMLDivElement>) => {
    const incoming = pickFirstFile(event.clipboardData.files)
    if (!incoming) {
      return
    }
    event.preventDefault()
    stageIncomingFile(incoming)
  }

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragActive(true)
  }

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragActive(false)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragActive(false)
    stageIncomingFile(pickFirstFile(event.dataTransfer.files))
  }

  const handleDropzoneKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return
    }
    event.preventDefault()
    inputRef.current?.click()
  }

  const handleUpload = () => {
    if (!file) {
      return
    }

    upload.mutate(
      {
        file,
      },
      {
        onSuccess: () => {
          resetComposer()
        },
      },
    )
  }

  return (
    <SectionCard
      variant="surface"
      title="Document Intake"
      description="Upload statements, receipts, screenshots, invoices, and exports here. Jenny should figure out the document type, source, and likely account on her own, then ask only for the gaps."
    >
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-2xl border border-dashed border-primary/30 bg-primary/5 p-5">
          <p className="text-sm font-semibold text-text">Stage a document</p>
          <div className="mt-4 space-y-4">
            <div
              role="button"
              tabIndex={0}
              onPaste={handlePaste}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onKeyDown={handleDropzoneKeyDown}
              className={[
                'rounded-2xl border border-dashed px-4 py-5 text-sm outline-none transition-colors',
                isDragActive
                  ? 'border-primary bg-primary/10 text-text'
                  : 'border-border/60 bg-surface/70 text-text-muted',
              ].join(' ')}
            >
              <p className="font-medium text-text">Paste or drop screenshots here</p>
              <p className="mt-1">
                Use <span className="font-medium text-text">Ctrl+V</span> after a screenshot, drag files in,
                or use the picker below.
              </p>
              {file ? (
                <p className="mt-3 text-text">
                  Ready to upload: <span className="font-medium">{file.name}</span>
                </p>
              ) : null}
            </div>
            <div>
              <Label htmlFor="document-file">File</Label>
              <Input
                id="document-file"
                ref={inputRef}
                type="file"
                accept=".pdf,.csv,.ofx,.qfx,.png,.jpg,.jpeg,.heic,.webp,.txt,.json,image/*,application/pdf,text/plain,text/csv"
                onChange={(event) => stageIncomingFile(event.target.files?.[0] ?? null)}
              />
            </div>
            <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4 text-sm text-text-muted">
              Jenny will infer the source, document type, and likely account label from the file contents, filename, and screenshot evidence.
              If anything is ambiguous, she will open a short follow-up question in the household plan queue.
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
                    {document.reviewSummary ? (
                      <p className="mt-2 text-sm text-text-muted">{document.reviewSummary}</p>
                    ) : null}
                  </div>
                  <div className="text-right text-xs text-text-muted">
                    <p>{document.status.replaceAll('_', ' ')}</p>
                    {document.reviewStatus ? (
                      <p className="mt-1">
                        Jenny: {document.reviewStatus.replaceAll('_', ' ')}
                        {document.reviewConfidence != null
                          ? ` (${Math.round(document.reviewConfidence * 100)}%)`
                          : ''}
                      </p>
                    ) : null}
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
