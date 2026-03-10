import { describe, expect, it } from 'vitest'
import {
  formatResolvedValue,
  numberInput,
  parseNullableNumber,
  questionSourceLabel,
} from './household-profile-utils'

describe('household profile utils', () => {
  it('formats nullable numbers consistently', () => {
    expect(numberInput(null)).toBe('')
    expect(numberInput(42)).toBe('42')
    expect(parseNullableNumber(' 1250 ')).toBe(1250)
    expect(parseNullableNumber('')).toBeNull()
    expect(parseNullableNumber('abc')).toBeNull()
  })

  it('formats resolved values for age and currency fields', () => {
    expect(
      formatResolvedValue({
        fieldName: 'target_retirement_age',
        label: 'Retirement age',
        value: '60',
        confidence: null,
        status: 'confirmed',
        source: 'manual',
        rationale: null,
        question: null,
      }),
    ).toBe('Age 60')

    expect(
      formatResolvedValue({
        fieldName: 'monthly_net_income_target',
        label: 'Income',
        value: '7500',
        confidence: null,
        status: 'confirmed',
        source: 'manual',
        rationale: null,
        question: null,
      }),
    ).toContain('$7,500')
  })

  it('prefers merchant and account context for question source labels', () => {
    expect(
      questionSourceLabel({
        id: 'question-1',
        fieldName: null,
        status: 'open',
        priority: 'high',
        question: 'What is this purchase?',
        rationale: null,
        recommendation: null,
        answerText: null,
        sourceDocumentId: 'doc-1',
        metadata: {
          sourceDocument: {
            merchant: 'Walmart',
            filename: 'receipt.pdf',
          },
        },
        createdAt: '2026-03-09T00:00:00Z',
        answeredAt: null,
      }),
    ).toBe('Walmart')
  })
})
