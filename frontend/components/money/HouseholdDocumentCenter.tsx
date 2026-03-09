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
  const [files, setFiles] = useState<File[]>([])
  const [isDragActive, setIsDragActive] = useState(false)

  const resetComposer = () => {
    setFiles([])
    setIsDragActive(false)
    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }

  const pickFiles = (incoming: FileList | File[] | null | undefined): File[] => {
    if (!incoming || incoming.length === 0) {
      return []
    }
    return Array.from(incoming).filter((file) => file.size > 0)
  }

  const stageIncomingFiles = (incoming: File[]) => {
    if (incoming.length === 0) {
      return
    }
    setFiles((current) => {
      const next = [...current]
      for (const file of incoming) {
        const alreadyQueued = next.some(
          (existing) =>
            existing.name === file.name &&
            existing.size === file.size &&
            existing.lastModified === file.lastModified,
        )
        if (!alreadyQueued) {
          next.push(file)
        }
      }
      return next
    })
  }

  const handlePaste = (event: ClipboardEvent<HTMLDivElement>) => {
    const incoming = pickFiles(event.clipboardData.files)
    if (incoming.length === 0) {
      return
    }
    event.preventDefault()
    stageIncomingFiles(incoming)
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
    stageIncomingFiles(pickFiles(event.dataTransfer.files))
  }

  const handleDropzoneKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return
    }
    event.preventDefault()
    inputRef.current?.click()
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      return
    }

    try {
      await Promise.all(files.map((file) => upload.mutateAsync({ file })))
      resetComposer()
    } catch {
      // Mutation hook already surfaces the upload error.
    }
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
              {files.length > 0 ? (
                <div className="mt-3 space-y-1 text-text">
                  <p className="font-medium">
                    Ready to upload: {files.length} file{files.length === 1 ? '' : 's'}
                  </p>
                  {files.slice(0, 5).map((file) => (
                    <p key={`${file.name}-${file.lastModified}`} className="text-sm">
                      {file.name}
                    </p>
                  ))}
                  {files.length > 5 ? (
                    <p className="text-sm text-text-muted">+{files.length - 5} more</p>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div>
              <Label htmlFor="document-file">File</Label>
              <Input
                id="document-file"
                ref={inputRef}
                type="file"
                multiple
                accept=".pdf,.csv,.ofx,.qfx,.png,.jpg,.jpeg,.heic,.webp,.txt,.json,image/*,application/pdf,text/plain,text/csv"
                onChange={(event) => stageIncomingFiles(pickFiles(event.target.files))}
              />
            </div>
            <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4 text-sm text-text-muted">
              Jenny will infer the source, document type, and likely account label from the file contents, filename, and screenshot evidence.
              If anything is ambiguous, she will open a short follow-up question in the household plan queue.
            </div>
            <Button onClick={() => void handleUpload()} disabled={files.length === 0 || upload.isPending}>
              {upload.isPending
                ? 'Uploading...'
                : files.length > 1
                  ? 'Stage Documents'
                  : 'Stage Document'}
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
