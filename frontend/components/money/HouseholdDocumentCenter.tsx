'use client'

import { useRef, useState } from 'react'
import type { ClipboardEvent, DragEvent, KeyboardEvent } from 'react'
import type {
  HouseholdDocument,
  HouseholdDocumentRequirement,
  ImportCenter,
} from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useUploadHouseholdDocument } from '@/lib/hooks/useHousehold'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import { formatEnumLabel, formatFileSize } from './formatters'

export function HouseholdDocumentCenter({
  documents,
  importCenter,
  documentRequirements = [],
}: {
  documents: HouseholdDocument[]
  importCenter?: ImportCenter
  documentRequirements?: HouseholdDocumentRequirement[]
}) {
  const upload = useUploadHouseholdDocument()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [isDragActive, setIsDragActive] = useState(false)
  const [dedupedCount, setDedupedCount] = useState(0)

  const resetComposer = () => {
    setFiles([])
    setIsDragActive(false)
    setDedupedCount(0)
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

  const pickDraggedFiles = (event: DragEvent<HTMLDivElement>): File[] => {
    const fromFiles = pickFiles(event.dataTransfer.files)
    if (fromFiles.length > 0) {
      return fromFiles
    }
    const fromItems = Array.from(event.dataTransfer.items ?? [])
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter((file): file is File => file != null && file.size > 0)
    return fromItems
  }

  const stageIncomingFiles = (incoming: File[]) => {
    if (incoming.length === 0) {
      return
    }
    setFiles((current) => {
      const next = [...current]
      let duplicates = 0
      for (const file of incoming) {
        const alreadyQueued = next.some(
          (existing) =>
            existing.name === file.name &&
            existing.size === file.size &&
            existing.lastModified === file.lastModified,
        )
        if (!alreadyQueued) {
          next.push(file)
        } else {
          duplicates += 1
        }
      }
      setDedupedCount((currentCount) => currentCount + duplicates)
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
    stageIncomingFiles(pickDraggedFiles(event))
  }

  const handleDropzoneKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return
    }
    event.preventDefault()
    inputRef.current?.click()
  }

  const handleDropzoneClick = () => {
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
              aria-label="Paste, drop, or choose household documents to upload"
              onPaste={handlePaste}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onKeyDown={handleDropzoneKeyDown}
              onClick={handleDropzoneClick}
              className={[
                'rounded-2xl border border-dashed px-4 py-5 text-sm outline-none transition-colors',
                isDragActive
                  ? 'border-primary bg-primary/10 text-text'
                  : 'border-border/60 bg-surface/70 text-text-muted',
              ].join(' ')}
            >
              <p className="font-medium text-text">Paste or drop screenshots or files here</p>
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
            {dedupedCount > 0 ? (
              <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-text-muted">
                Skipped {dedupedCount} duplicate file{dedupedCount === 1 ? '' : 's'} already in the upload queue.
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={() => void handleUpload()}
                disabled={files.length === 0 || upload.isPending}
                aria-busy={upload.isPending}
              >
                {upload.isPending
                  ? 'Uploading...'
                  : files.length > 1
                    ? 'Upload Documents'
                    : 'Upload Document'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={resetComposer}
                disabled={files.length === 0 || upload.isPending}
                aria-busy={upload.isPending}
              >
                Clear Queue
              </Button>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          {importCenter ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Intake coverage
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {importCenter.trackedDocuments}
                </p>
                <p className="mt-1 text-sm text-text-muted">
                  {importCenter.parsedDocuments} parsed so far
                </p>
              </div>
              <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Next best uploads
                </p>
                {importCenter.suggestedFirstUploads.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {importCenter.suggestedFirstUploads.map((item) => (
                      <Badge key={item} variant="outline">
                        {item}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-text-muted">
                    Intake guidance appears after Jenny sees gaps in the household record.
                  </p>
                )}
              </div>
            </div>
          ) : null}

          {importCenter?.automations.length ? (
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-sm font-semibold text-text">What Jenny will automate</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {importCenter.automations.map((automation) => (
                  <Badge key={automation} variant="secondary">
                    {automation}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}

          {importCenter?.supportedDocuments.length ? (
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-sm font-semibold text-text">Supported document types</p>
              <div className="mt-3 space-y-3">
                {importCenter.supportedDocuments.map((documentType) => (
                  <div key={documentType.label}>
                    <p className="text-sm font-medium text-text">{documentType.label}</p>
                    <p className="mt-1 text-sm text-text-muted">
                      Formats: {documentType.formats.join(', ')}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      Extracts: {documentType.extracts.join(', ')}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {documentRequirements.length > 0 ? (
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-sm font-semibold text-text">Planning document placeholders</p>
              <div className="mt-3 space-y-3">
                {documentRequirements.slice(0, 6).map((requirement) => (
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
          ) : null}

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
                      {formatEnumLabel(document.sourceType, 'Source pending')} ·{' '}
                      {formatEnumLabel(document.documentType, 'Type pending')}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge variant="secondary">
                        {formatEnumLabel(document.status, 'staged')}
                      </Badge>
                      {document.classificationConfidence != null ? (
                        <Badge variant="outline">
                          Classifier {Math.round(document.classificationConfidence * 100)}%
                        </Badge>
                      ) : null}
                    </div>
                    {document.accountLabel ? (
                      <p className="mt-1 text-sm text-text-muted">{document.accountLabel}</p>
                    ) : null}
                    {document.reviewSummary ? (
                      <p className="mt-2 text-sm text-text-muted">{document.reviewSummary}</p>
                    ) : null}
                    <p className="mt-2 text-xs text-text-muted">
                      Uploaded {formatRelativeTime(document.uploadedAt)}
                      {document.parsedAt ? ` · Parsed ${formatRelativeTime(document.parsedAt)}` : ''}
                    </p>
                    {(document.statementStart && document.statementEnd) ? (
                      <p className="mt-1 text-xs text-text-muted">
                        Statement window {formatDate(document.statementStart, true)} to{' '}
                        {formatDate(document.statementEnd, true)}
                      </p>
                    ) : document.statementStart ? (
                      <p className="mt-1 text-xs text-text-muted">
                        Statement start {formatDate(document.statementStart, true)}
                      </p>
                    ) : document.statementEnd ? (
                      <p className="mt-1 text-xs text-text-muted">
                        Statement end {formatDate(document.statementEnd, true)}
                      </p>
                    ) : null}
                  </div>
                  <div className="text-right text-xs text-text-muted">
                    {document.reviewStatus ? (
                      <p className="mt-1">
                        Jenny: {formatEnumLabel(document.reviewStatus)}
                        {document.reviewConfidence != null
                          ? ` (${Math.round(document.reviewConfidence * 100)}%)`
                          : ''}
                      </p>
                    ) : null}
                    <p className="mt-1">{formatFileSize(document.fileSizeBytes)}</p>
                    {document.contentType ? <p className="mt-1">{document.contentType}</p> : null}
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
