import type {
  HouseholdQuestion,
  HouseholdResolvedValue,
} from '@/lib/api/household'
import { formatCurrency } from './formatters'

export type QuestionSourceDocument = {
  id?: string | null
  filename?: string | null
  sourceType?: string | null
  documentType?: string | null
  accountLabel?: string | null
  reviewSummary?: string | null
  merchant?: string | null
  accountHint?: string | null
}

export function numberInput(value: number | null): string {
  return value == null ? '' : String(value)
}

export function parseNullableNumber(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

export function formatResolvedValue(value: HouseholdResolvedValue): string {
  if (value.value == null || value.value === '') {
    return 'Waiting on more evidence'
  }
  if (value.fieldName === 'target_retirement_age') {
    return `Age ${value.value}`
  }
  const numeric = Number(value.value)
  return Number.isFinite(numeric) ? formatCurrency(numeric) : value.value
}

export function getQuestionSourceDocument(question: HouseholdQuestion): QuestionSourceDocument | null {
  const sourceDocument = question.metadata.sourceDocument
  if (!sourceDocument || typeof sourceDocument !== 'object') {
    return null
  }
  return sourceDocument as QuestionSourceDocument
}

export function questionSourceLabel(question: HouseholdQuestion): string {
  const sourceDocument = getQuestionSourceDocument(question)
  if (!sourceDocument) {
    return 'Source document unavailable'
  }
  if (sourceDocument.merchant) {
    return sourceDocument.merchant
  }
  if (sourceDocument.accountLabel) {
    return sourceDocument.accountLabel
  }
  if (sourceDocument.accountHint) {
    return sourceDocument.accountHint
  }
  if (sourceDocument.filename) {
    return sourceDocument.filename
  }
  return 'Source document unavailable'
}
