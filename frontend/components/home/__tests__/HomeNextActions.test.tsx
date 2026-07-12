import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { HomeActionItem, HomeActionQueue } from '@/lib/api/home'
import { HomeActionQueueProvider } from '../../providers/HomeActionQueueProvider'
import { HomeActionQueueBadge } from '../HomeActionQueueBadge'
import { HomeNextActions } from '../HomeNextActions'

const useHomeActionQueueMock = vi.fn()
const acknowledgeMutateMock = vi.fn()
const transitionMutateMock = vi.fn()

vi.mock('@/lib/hooks/useHomeActionQueue', () => ({
  useHomeActionQueue: (options?: { enabled?: boolean }) =>
    useHomeActionQueueMock(options),
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useAcknowledgeJennyNotification: () => ({
    mutate: acknowledgeMutateMock,
    isPending: false,
  }),
}))

vi.mock('@/lib/hooks/useSymbolIntelligence', () => ({
  useTransitionSymbolWorkflow: () => ({
    mutate: transitionMutateMock,
    isPending: false,
  }),
}))

function buildAction(
  id: string,
  overrides: Partial<HomeActionItem> = {},
): HomeActionItem {
  return {
    id,
    source: 'household',
    category: 'household',
    priority: 'high',
    title: `Action ${id}`,
    detail: `Detail for ${id}`,
    actionLabel: `Open ${id}`,
    href: `/money?tab=${id}`,
    symbol: null,
    badge: 'Needs review',
    ...overrides,
  }
}

function buildQueue(actions: HomeActionItem[]): HomeActionQueue {
  return {
    generatedAt: '2026-07-12T12:00:00Z',
    summary: `${actions.length} decisions need attention.`,
    actions,
  }
}

function renderQueue(children: ReactNode) {
  return render(
    <HomeActionQueueProvider enabled>{children}</HomeActionQueueProvider>,
  )
}

describe('HomeNextActions', () => {
  const refetch = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    useHomeActionQueueMock.mockReturnValue({
      data: buildQueue([]),
      isLoading: false,
      isFetching: false,
      error: null,
      refetch,
    })
  })

  it('shares one queue query with the badge and surfaces concise deep links', () => {
    const actions = [
      buildAction('budget'),
      buildAction('holdings'),
      buildAction('review'),
      buildAction('fourth'),
    ]
    useHomeActionQueueMock.mockReturnValue({
      data: buildQueue(actions),
      isLoading: false,
      isFetching: false,
      error: null,
      refetch,
    })

    renderQueue(
      <>
        <HomeActionQueueBadge />
        <HomeNextActions />
      </>,
    )

    expect(useHomeActionQueueMock).toHaveBeenCalledTimes(1)
    const section = screen.getByRole('region', { name: 'Next actions' })
    expect(
      within(section).getByRole('link', { name: 'Open budget' }),
    ).toHaveAttribute('href', '/money?tab=budget')
    expect(within(section).queryByText('Action fourth')).not.toBeInTheDocument()
    expect(
      within(section).getByText('1 more action in the Actions menu.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Action Queue, 4 open' }),
    ).toBeInTheDocument()
  })

  it('shows an accessible loading state', () => {
    useHomeActionQueueMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isFetching: true,
      error: null,
      refetch,
    })

    renderQueue(<HomeNextActions />)

    expect(screen.getByRole('status')).toHaveTextContent(
      'Loading next actions.',
    )
    expect(screen.getByText('Loading')).toBeInTheDocument()
  })

  it('keeps Today usable and offers a focused retry when the queue fails', async () => {
    const user = userEvent.setup()
    useHomeActionQueueMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('Queue failed'),
      refetch,
    })

    renderQueue(
      <>
        <HomeActionQueueBadge />
        <HomeNextActions />
      </>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Next actions unavailable',
    )
    expect(
      screen.getByRole('button', { name: 'Action Queue, unavailable' }),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry next actions' }))
    expect(refetch).toHaveBeenCalledTimes(1)
  })

  it('shows an all-clear state when there is nothing to do', () => {
    renderQueue(<HomeNextActions />)

    expect(screen.getByRole('status')).toHaveTextContent('All clear')
    expect(screen.getByText('0 open')).toBeInTheDocument()
  })

  it('clears a quick action once for both inline and badge surfaces', async () => {
    const user = userEvent.setup()
    const action = buildAction('alert', {
      title: 'Review Jenny alert',
      execution: {
        kind: 'acknowledge_notification',
        notificationId: 'notification-1',
        symbol: null,
        stage: null,
      },
    })
    useHomeActionQueueMock.mockReturnValue({
      data: buildQueue([action]),
      isLoading: false,
      isFetching: false,
      error: null,
      refetch,
    })
    acknowledgeMutateMock.mockImplementation(
      (_notificationId: string, options?: { onSuccess?: () => void }) =>
        options?.onSuccess?.(),
    )

    renderQueue(
      <>
        <HomeActionQueueBadge />
        <HomeNextActions />
      </>,
    )

    await user.click(screen.getByRole('button', { name: 'Dismiss alert' }))

    expect(screen.queryByText('Review Jenny alert')).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Action Queue, 0 open' }),
    ).toBeInTheDocument()
    expect(acknowledgeMutateMock).toHaveBeenCalledWith(
      'notification-1',
      expect.any(Object),
    )
  })
})
