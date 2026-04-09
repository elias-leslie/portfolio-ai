'use client'

import { useRef, useState } from 'react'
import type { ClipboardEvent, DragEvent, KeyboardEvent } from 'react'
import { toast } from 'sonner'
import type {
  HouseholdDocument,
  HouseholdDocumentRequirement,
  HouseholdEvidenceAccount,
  ImportCenter,
} from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useUploadHouseholdDocument } from '@/lib/hooks/useHousehold'
import { ImportCenterSidebar } from './ImportCenterSidebar'

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 // 50 MB

export function HouseholdDocumentCenter({
  documents,
  importCenter,
  documentRequirements = [],
  evidenceAccounts = [],
}: {
  documents: HouseholdDocument[]
  importCenter?: ImportCenter
  documentRequirements?: HouseholdDocumentRequirement[]
  evidenceAccounts?: HouseholdEvidenceAccount[]
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
    if (inputRef.current) inputRef.current.value = ''
  }

  const pickFiles = (incoming: FileList | File[] | null | undefined): File[] => {
    if (!incoming || incoming.length === 0) return []
    const valid: File[] = []
    for (const file of Array.from(incoming)) {
      if (file.size === 0) continue
      if (file.size > MAX_FILE_SIZE_BYTES) {
        toast.error(`${file.name} exceeds the 50 MB limit and was skipped.`)
        continue
      }
      valid.push(file)
    }
    return valid
  }

  const pickDraggedFiles = (event: DragEvent<HTMLDivElement>): File[] => {
    const fromFiles = pickFiles(event.dataTransfer.files)
    if (fromFiles.length > 0) return fromFiles
    return Array.from(event.dataTransfer.items ?? [])
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter((file): file is File => file != null && file.size > 0)
  }

  const stageIncomingFiles = (incoming: File[]) => {
    if (incoming.length === 0) return
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
        if (!alreadyQueued) next.push(file)
        else duplicates += 1
      }
      setDedupedCount((c) => c + duplicates)
      return next
    })
  }

  const handlePaste = (event: ClipboardEvent<HTMLDivElement>) => {
    const incoming = pickFiles(event.clipboardData.files)
    if (incoming.length === 0) return
    event.preventDefault()
    stageIncomingFiles(incoming)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragActive(false)
    stageIncomingFiles(pickDraggedFiles(event))
  }

  const handleDropzoneKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    inputRef.current?.click()
  }

  const handleUpload = async () => {
    if (files.length === 0) return
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
      title="Evidence Intake"
      description="Drop financial files here once. Jenny should decide what they are, what matters, and whether they belong in cash-flow, portfolio, planning, or reference context, then ask only for missing context."
    >
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-2xl border border-dashed border-primary/30 bg-primary/5 p-5">
          <p className="text-sm font-semibold text-text">Drop evidence once</p>
          <div className="mt-4 space-y-4">
            <div
              role="button"
              tabIndex={0}
              aria-label="Paste, drop, or choose household documents to upload"
              onPaste={handlePaste}
              onDragOver={(e) => { e.preventDefault(); setIsDragActive(true) }}
              onDragLeave={(e) => { e.preventDefault(); setIsDragActive(false) }}
              onDrop={handleDrop}
              onKeyDown={handleDropzoneKeyDown}
              onClick={() => inputRef.current?.click()}
              className={[
                'rounded-2xl border border-dashed px-4 py-5 text-sm outline-none transition-colors',
                isDragActive
                  ? 'border-primary bg-primary/10 text-text'
                  : 'border-border/60 bg-surface/70 text-text-muted',
              ].join(' ')}
            >
              <p className="font-medium text-text">Paste or drop screenshots or files here</p>
              <p className="mt-1">
                Use <span className="font-medium text-text">{typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.userAgent) ? '\u2318V' : 'Ctrl+V'}</span> after a screenshot, drag files in,
                or use the picker below.
              </p>
              {files.length > 0 ? (
                <div className="mt-3 space-y-1 text-text">
                  <p className="font-medium">Ready to upload: {files.length} file{files.length === 1 ? '' : 's'}</p>
                  {files.slice(0, 5).map((file) => (
                    <p key={`${file.name}-${file.lastModified}`} className="text-sm">{file.name}</p>
                  ))}
                  {files.length > 5 ? <p className="text-sm text-text-muted">+{files.length - 5} more</p> : null}
                </div>
              ) : null}
            </div>
            <div>
              <Label htmlFor="document-file">Files</Label>
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
              Jenny will infer the source, document type, likely account, and where this belongs in your system from the file contents, filename, and screenshot evidence.
              If anything materially changes the outcome, she will open one short follow-up instead of sending you through separate upload flows.
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
                {upload.isPending ? 'Uploading...' : files.length > 1 ? 'Upload Documents' : 'Upload Document'}
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

        <ImportCenterSidebar
          documents={documents}
          importCenter={importCenter}
          documentRequirements={documentRequirements}
          evidenceAccounts={evidenceAccounts}
        />
      </div>
    </SectionCard>
  )
}
