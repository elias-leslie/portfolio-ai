import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { JennyQuestionInbox } from '../JennyQuestionInbox'

const answerMutate = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useAnswerHouseholdQuestion: () => ({
    mutate: answerMutate,
    isPending: false,
  }),
}))

describe('JennyQuestionInbox', () => {
  beforeEach(() => {
    answerMutate.mockReset()
  })

  it('renders boolean questions with yes/no actions', async () => {
    const user = userEvent.setup()

    render(
      <JennyQuestionInbox
        questions={[
          {
            id: 'question-1',
            fieldName: 'monthlyEssentialTarget',
            status: 'open',
            priority: 'high',
            question: 'Is this your primary household checking account?',
            rationale: null,
            recommendation:
              'Answer yes if most household cash flow passes through here.',
            answerText: null,
            sourceDocumentId: 'doc-1',
            questionFormat: 'boolean',
            options: null,
            direction: 'jenny_to_user',
            metadata: {
              sourceDocument: {
                filename: 'checking.pdf',
                accountLabel: 'Joint Checking',
              },
            },
            createdAt: '2026-03-11T00:00:00Z',
            answeredAt: null,
          },
        ]}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Yes' }))

    expect(answerMutate).toHaveBeenCalledWith(
      { questionId: 'question-1', answerText: 'yes' },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    )
  })

  it('renders select options and submits the chosen answer', async () => {
    const user = userEvent.setup()

    render(
      <JennyQuestionInbox
        questions={[
          {
            id: 'question-2',
            fieldName: null,
            status: 'open',
            priority: 'medium',
            question: 'What best describes this household?',
            rationale: null,
            recommendation: null,
            answerText: null,
            sourceDocumentId: null,
            questionFormat: 'single_select',
            options: ['Single income', 'Dual income', 'Retired'],
            direction: 'jenny_to_user',
            metadata: {},
            createdAt: '2026-03-11T00:00:00Z',
            answeredAt: null,
          },
        ]}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Dual income' }))

    expect(answerMutate).toHaveBeenCalledWith(
      { questionId: 'question-2', answerText: 'Dual income' },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    )
  })
})
