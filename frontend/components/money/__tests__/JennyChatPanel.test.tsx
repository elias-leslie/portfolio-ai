import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { JennyChatPanel } from '../JennyChatPanel'

const mutateAsync = vi.fn()

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useJennyChat: () => ({
    mutateAsync,
    isPending: false,
  }),
}))

describe('JennyChatPanel', () => {
  beforeEach(() => {
    mutateAsync.mockReset()
    window.localStorage.clear()
  })

  it('sends a free-form message and renders Jenny reply', async () => {
    const user = userEvent.setup()
    mutateAsync.mockResolvedValue({
      reply: 'Jenny says AMD still looks constructive.',
      sessionId: 'session-1',
      resolvedQuestions: [],
      updatedFields: [],
      referencedSymbols: ['AMD'],
    })

    render(<JennyChatPanel />)

    await user.type(
      screen.getByPlaceholderText(/ask anything about portfolio-ai/i),
      'What does Jenny think about AMD?',
    )
    await user.click(screen.getByRole('button', { name: /send to jenny/i }))

    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        message: 'What does Jenny think about AMD?',
        sessionId: null,
      }),
    )
    expect(
      await screen.findByText('Jenny says AMD still looks constructive.'),
    ).toBeInTheDocument()
  })

  it('shows when Jenny reconciled household questions from chat', async () => {
    const user = userEvent.setup()
    mutateAsync.mockResolvedValue({
      reply: 'I set your retirement age to 60.',
      sessionId: 'session-2',
      resolvedQuestions: [
        {
          id: 'question-1',
          fieldName: 'target_retirement_age',
          question: 'What age do you want to retire?',
          answerText: '60',
        },
      ],
      updatedFields: ['target_retirement_age'],
      referencedSymbols: [],
    })

    render(<JennyChatPanel />)

    await user.type(
      screen.getByPlaceholderText(/ask anything about portfolio-ai/i),
      'I want to retire at 60.',
    )
    await user.click(screen.getByRole('button', { name: /send to jenny/i }))

    expect(
      await screen.findByText(/jenny reconciled 1 question/i),
    ).toBeInTheDocument()
  })

  it('keeps the draft and empty-state history intact when Jenny chat fails', async () => {
    const user = userEvent.setup()
    mutateAsync.mockRejectedValueOnce(new Error('chat failed'))

    render(<JennyChatPanel />)

    await user.type(
      screen.getByPlaceholderText(/ask anything about portfolio-ai/i),
      'Please try this again.',
    )
    await user.click(screen.getByRole('button', { name: /send to jenny/i }))

    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        message: 'Please try this again.',
        sessionId: null,
      }),
    )

    expect(
      screen.getByPlaceholderText(/ask anything about portfolio-ai/i),
    ).toHaveValue('Please try this again.')
    expect(
      screen.getByText(/Jenny could not reply yet\. chat failed/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Try: "What does Jenny think about AMD\?"/i),
    ).toBeInTheDocument()
    expect(window.localStorage.getItem('portfolio-ai:jenny-chat:history')).toBe(
      '[]',
    )
  })

  it('clears the error message once the user edits the draft', async () => {
    const user = userEvent.setup()
    mutateAsync.mockRejectedValueOnce(new Error('chat failed'))

    render(<JennyChatPanel />)

    const input = screen.getByPlaceholderText(
      /ask anything about portfolio-ai/i,
    )
    await user.type(input, 'Retry this')
    await user.click(screen.getByRole('button', { name: /send to jenny/i }))

    expect(
      await screen.findByText(/Jenny could not reply yet\. chat failed/i),
    ).toBeInTheDocument()

    await user.type(input, ' please')

    expect(
      screen.queryByText(/Jenny could not reply yet\. chat failed/i),
    ).not.toBeInTheDocument()
  })
})
