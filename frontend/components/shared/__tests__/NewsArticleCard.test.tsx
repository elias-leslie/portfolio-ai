import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NewsArticleCard } from '../NewsArticleCard'

const useArticleFeedbackMock = vi.fn()
const submitFeedbackMutate = vi.fn()

vi.mock('@/lib/hooks/useNews', () => ({
  useArticleFeedback: (...args: unknown[]) => useArticleFeedbackMock(...args),
  useSubmitArticleFeedback: () => ({
    mutate: submitFeedbackMutate,
    isPending: false,
    variables: undefined,
  }),
}))

describe('NewsArticleCard', () => {
  beforeEach(() => {
    useArticleFeedbackMock.mockReset()
    submitFeedbackMutate.mockReset()
    useArticleFeedbackMock.mockReturnValue({
      data: { exists: false },
    })
  })

  it('submits useful feedback for articles with feedback metadata', async () => {
    const user = userEvent.setup()

    render(
      <NewsArticleCard
        index={0}
        article={{
          headline: 'Apple launches a new product',
          articleHash: 'aapl-hash',
          url: 'https://example.com/aapl',
          vendor: 'rss',
          publishedAt: '2026-03-12T12:00:00Z',
        }}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: 'Mark article as useful' }),
    )

    expect(submitFeedbackMutate).toHaveBeenCalledWith({
      articleUrl: 'https://example.com/aapl',
      articleHash: 'aapl-hash',
      vendor: 'rss',
      isUseful: true,
    })
  })

  it('shows the saved feedback state from the query', () => {
    useArticleFeedbackMock.mockReturnValue({
      data: {
        exists: true,
        isUseful: false,
      },
    })

    render(
      <NewsArticleCard
        index={0}
        article={{
          headline: 'Apple launches a new product',
          articleHash: 'aapl-hash',
          url: 'https://example.com/aapl',
          vendor: 'rss',
        }}
      />,
    )

    expect(screen.getByText('Marked not useful')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Mark article as not useful' }),
    ).toHaveAttribute('aria-pressed', 'true')
  })

  it('hides feedback controls when required feedback metadata is missing', () => {
    render(
      <NewsArticleCard
        index={0}
        article={{
          headline: 'Apple launches a new product',
          url: 'https://example.com/aapl',
        }}
      />,
    )

    expect(
      screen.queryByRole('button', { name: 'Mark article as useful' }),
    ).not.toBeInTheDocument()
  })
})
