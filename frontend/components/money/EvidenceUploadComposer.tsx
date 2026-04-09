'use client'

import type { ClipboardEvent, DragEvent, KeyboardEvent } from 'react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useUploadHouseholdDocument } from '@/lib/hooks/useHousehold'

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

interface EvidenceUploadComposerProps {
  title: string
  description: string
  accountLabel?: string | null
  compact?: boolean
}

export function EvidenceUploadComposer({
  title,
  description,
  accountLabel = null,
  compact = false,
}: EvidenceUploadComposerProps) {
  const upload = useUploadHouseholdDocument()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [isDragActive, setIsDragActive] = useState(false)
  const [dedupedCount, setDedupedCount] = useState(0)
  const inputId = `${accountLabel ?? title}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'evidence-file'

  const resetComposer = () => {
    setFiles([])
    setIsDragActive(false)
    setDedupedCount(0)
    if (inputRef.current) inputRef.current.value = ''
  }

  const pickFiles = (
    incoming: FileList | File[] | null | undefined,
  ): File[] => {
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
      setDedupedCount((count) => count + duplicates)
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
      await Promise.all(
        files.map((file) =>
          upload.mutateAsync({
            file,
            accountLabel: accountLabel ?? undefined,
          }),
        ),
      )
      resetComposer()
    } catch {
      // Upload hook already surfaces the error toast.
    }
  }

  return (
    <div
      className={[
        'rounded-2xl border bg-surface-muted/15',
        accountLabel
          ? 'border-primary/25 bg-primary/5'
          : 'border-border/40',
        compact ? 'p-4' : 'p-5',
      ].join(' ')}
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-text">{title}</p>
          <p className="mt-1 text-sm text-text-muted">{description}</p>
        </div>
        {accountLabel ? (
          <span className="rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            Hint: {accountLabel}
          </span>
        ) : null}
      </div>

      <div className="mt-4 space-y-4">
        <div
          role="button"
          tabIndex={0}
          aria-label="Paste, drop, or choose evidence files to upload"
          onPaste={handlePaste}
          onDragOver={(event) => {
            event.preventDefault()
            setIsDragActive(true)
          }}
          onDragLeave={(event) => {
            event.preventDefault()
            setIsDragActive(false)
          }}
          onDrop={handleDrop}
          onKeyDown={handleDropzoneKeyDown}
          onClick={() => inputRef.current?.click()}
          className={[
            'rounded-2xl border border-dashed px-4 text-sm outline-none transition-colors',
            compact ? 'py-4' : 'py-5',
            isDragActive
              ? 'border-primary bg-primary/10 text-text'
              : accountLabel
                ? 'border-primary/35 bg-surface/80 text-text-muted'
              : 'border-border/60 bg-surface/70 text-text-muted',
          ].join(' ')}
        >
          <p className="font-medium text-text">
            {accountLabel
              ? 'Drop account evidence here'
              : 'Paste or drop screenshots or files here'}
          </p>
          <p className="mt-1">
            {accountLabel
              ? 'Jenny will use the selected account as a routing hint, then verify the actual document contents before applying anything.'
              : 'Jenny will infer the account, financial area, and what to update from the file itself.'}
          </p>
          {files.length > 0 ? (
            <div className="mt-3 space-y-1 text-text">
              <p className="font-medium">
                Ready to upload: {files.length} file
                {files.length === 1 ? '' : 's'}
              </p>
              {files.slice(0, 4).map((file) => (
                <p
                  key={`${file.name}-${file.lastModified}`}
                  className="text-sm"
                >
                  {file.name}
                </p>
              ))}
              {files.length > 4 ? (
                <p className="text-sm text-text-muted">
                  +{files.length - 4} more
                </p>
              ) : null}
            </div>
          ) : null}
        </div>

        <div>
          <Label htmlFor={inputId}>Files</Label>
          <Input
            id={inputId}
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.csv,.ofx,.qfx,.png,.jpg,.jpeg,.heic,.webp,.txt,.json,image/*,application/pdf,text/plain,text/csv"
            onChange={(event) => stageIncomingFiles(pickFiles(event.target.files))}
          />
        </div>

        {dedupedCount > 0 ? (
          <div className="rounded-2xl border border-warning/30 bg-warning/10 p-3 text-sm text-text-muted">
            Skipped {dedupedCount} duplicate file
            {dedupedCount === 1 ? '' : 's'} already in the queue.
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
                ? 'Upload files'
                : 'Upload file'}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={resetComposer}
            disabled={files.length === 0 || upload.isPending}
            aria-busy={upload.isPending}
          >
            Clear
          </Button>
        </div>
      </div>
    </div>
  )
}
