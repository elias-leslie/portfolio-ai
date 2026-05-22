import { postForm } from '../client'
import type { HouseholdDocument, HouseholdDocumentUpload } from './types'

export const MAX_HOUSEHOLD_EVIDENCE_FILE_SIZE_BYTES = 50 * 1024 * 1024

const SUPPORTED_HOUSEHOLD_EVIDENCE_EXTENSIONS = new Set([
  '.bmp',
  '.csv',
  '.heic',
  '.htm',
  '.html',
  '.jpeg',
  '.jpg',
  '.json',
  '.ofx',
  '.pdf',
  '.png',
  '.qfx',
  '.txt',
  '.webp',
  '.xml',
])

const SUPPORTED_HOUSEHOLD_EVIDENCE_TYPES = new Set([
  'application/json',
  'application/octet-stream',
  'application/ofx',
  'application/pdf',
  'application/vnd.intu.qfx',
  'application/vnd.ms-excel',
  'application/x-ofx',
  'application/xml',
])

function householdEvidenceExtension(filename: string): string {
  const match = filename
    .trim()
    .toLowerCase()
    .match(/\.[^.]+$/)
  return match?.[0] ?? ''
}

function isSupportedHouseholdEvidenceMediaType(type: string): boolean {
  const normalized = type.split(';', 1)[0]?.trim().toLowerCase() ?? ''
  return (
    !normalized ||
    SUPPORTED_HOUSEHOLD_EVIDENCE_TYPES.has(normalized) ||
    normalized.startsWith('image/') ||
    normalized.startsWith('text/')
  )
}

export function validateHouseholdEvidenceFile(file: File): void {
  if (file.size === 0) {
    throw new Error(`${file.name} is empty.`)
  }
  if (file.size > MAX_HOUSEHOLD_EVIDENCE_FILE_SIZE_BYTES) {
    throw new Error(`${file.name} exceeds the 50 MB limit.`)
  }
  if (
    !SUPPORTED_HOUSEHOLD_EVIDENCE_EXTENSIONS.has(
      householdEvidenceExtension(file.name),
    ) ||
    !isSupportedHouseholdEvidenceMediaType(file.type)
  ) {
    throw new Error(
      `${file.name} is not a supported evidence file. Use PDF, CSV, OFX/QFX, image, text, JSON, XML, or HTML.`,
    )
  }
}

function resolveFile(payload: HouseholdDocumentUpload): File {
  if (payload.file) return payload.file
  const rawText = payload.rawText?.trim()
  if (rawText) {
    return new File([rawText], payload.filename?.trim() || 'pasted-evidence.txt', {
      type: 'text/plain',
    })
  }
  throw new Error('Upload requires a file or pasted text.')
}

function applySharedFormFields(
  form: FormData,
  payload: HouseholdDocumentUpload,
): void {
  if (payload.sourceType) form.append('source_type', payload.sourceType)
  if (payload.documentType) form.append('document_type', payload.documentType)
  if (payload.accountLabel) form.append('account_label', payload.accountLabel)
  if (payload.householdAccountId) form.append('household_account_id', payload.householdAccountId)
  if (payload.reviewSessionId) form.append('review_session_id', payload.reviewSessionId)
}

export async function uploadHouseholdDocument(
  payload: HouseholdDocumentUpload,
): Promise<HouseholdDocument> {
  const file = resolveFile(payload)
  validateHouseholdEvidenceFile(file)
  const form = new FormData()
  form.append('file', file)
  applySharedFormFields(form, payload)
  return postForm<HouseholdDocument>('/api/intake/evidence', form)
}

export async function uploadHouseholdDocuments(
  payloads: HouseholdDocumentUpload[],
): Promise<HouseholdDocument[]> {
  if (payloads.length === 0) {
    throw new Error('Upload requires at least one file or pasted text.')
  }
  const form = new FormData()
  for (const payload of payloads) {
    const file = resolveFile(payload)
    validateHouseholdEvidenceFile(file)
    form.append('files', file)
  }
  applySharedFormFields(form, payloads[0])
  return postForm<HouseholdDocument[]>('/api/intake/evidence/batch', form)
}
