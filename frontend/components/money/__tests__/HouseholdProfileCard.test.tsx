import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HouseholdProfileCard } from '../HouseholdProfileCard'

const mutate = vi.fn()
const answerMutate = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUpdateHouseholdProfile: () => ({
    mutate,
    isPending: false,
  }),
  useAnswerHouseholdQuestion: () => ({
    mutate: answerMutate,
    isPending: false,
  }),
}))

describe('HouseholdProfileCard', () => {
  it('submits the edited household plan', () => {
    render(
      <HouseholdProfileCard
        profile={{
          id: 'profile-1',
          householdName: 'Household',
          monthlyNetIncomeTarget: null,
          monthlyEssentialTarget: null,
          monthlyDiscretionaryTarget: null,
          monthlySavingsTarget: null,
          targetRetirementAge: null,
          targetRetirementSpend: null,
          notes: null,
          createdAt: '2026-03-09T00:00:00Z',
          updatedAt: '2026-03-09T00:00:00Z',
        }}
        resolvedValues={[
          {
            fieldName: 'monthlyNetIncomeTarget',
            label: 'Monthly take-home income',
            value: null,
            confidence: null,
            status: 'missing',
            source: 'unknown',
            rationale: null,
            question: null,
          },
        ]}
        questions={[]}
      />,
    )

    fireEvent.change(screen.getByLabelText(/household name/i), {
      target: { value: 'Kasadis Family' },
    })
    fireEvent.change(screen.getByLabelText(/monthly take-home income/i), {
      target: { value: '12500' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save overrides/i }))

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({
        householdName: 'Kasadis Family',
        monthlyNetIncomeTarget: 12500,
      }),
    )
  })

  it('shows source attribution and recommendations for Jenny questions', () => {
    render(
      <HouseholdProfileCard
        profile={{
          id: 'profile-1',
          householdName: 'Household',
          monthlyNetIncomeTarget: null,
          monthlyEssentialTarget: null,
          monthlyDiscretionaryTarget: null,
          monthlySavingsTarget: null,
          targetRetirementAge: null,
          targetRetirementSpend: null,
          notes: null,
          createdAt: '2026-03-09T00:00:00Z',
          updatedAt: '2026-03-09T00:00:00Z',
        }}
        resolvedValues={[]}
        questions={[
          {
            id: 'question-1',
            fieldName: null,
            status: 'open',
            priority: 'high',
            question: 'What kind of document is this and which account or merchant is it tied to?',
            rationale: 'Jenny could not confidently identify the institution, account, or document class from the file alone.',
            recommendation: 'Confirm that this is a Walmart order and should count as household shopping.',
            answerText: null,
            sourceDocumentId: 'doc-1',
            metadata: {
              sourceDocument: {
                filename: '1Order details - Walmart.com.pdf',
                merchant: 'Walmart',
                reviewSummary: 'Order details from Walmart with itemized household purchases.',
              },
            },
            createdAt: '2026-03-09T00:00:00Z',
            answeredAt: null,
          },
        ]}
      />,
    )

    expect(screen.getByText(/source: walmart/i)).toBeInTheDocument()
    expect(screen.getByText(/file: 1order details - walmart\.com\.pdf/i)).toBeInTheDocument()
    expect(screen.getByText(/jenny recommends:/i)).toBeInTheDocument()
    expect(
      screen.getByText(/confirm that this is a walmart order and should count as household shopping/i),
    ).toBeInTheDocument()
  })
})
