import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PushSubscriptionList } from '@/lib/api/push'
import type { DevicePushState } from '@/lib/hooks/usePushAlerts'
import { PushAlertsCard } from '../PushAlertsCard'

const subscriptionsState = {
  data: undefined as PushSubscriptionList | undefined,
  isLoading: false,
}
const deviceState = {
  current: {
    support: 'supported',
    permission: 'default',
    endpoint: null,
    isLoading: false,
  } as DevicePushState,
}

vi.mock('@/lib/hooks/usePushAlerts', () => ({
  usePushSubscriptions: () => subscriptionsState,
  useDevicePushState: () => deviceState.current,
  useEnablePushOnThisDevice: () => ({ mutate: vi.fn(), isPending: false }),
  useDisablePushOnThisDevice: () => ({ mutate: vi.fn(), isPending: false }),
  useRemovePushSubscription: () => ({ mutate: vi.fn(), isPending: false }),
  useSendTestPush: () => ({ mutate: vi.fn(), isPending: false }),
}))

function list(
  overrides: Partial<PushSubscriptionList> = {},
): PushSubscriptionList {
  return {
    enabled: true,
    publicKey: 'public-key',
    recipients: [
      { id: 'member-1', name: 'Elias' },
      { id: 'member-2', name: 'Mariana' },
    ],
    subscriptions: [],
    ...overrides,
  }
}

beforeEach(() => {
  subscriptionsState.data = list()
  subscriptionsState.isLoading = false
  deviceState.current = {
    support: 'supported',
    permission: 'default',
    endpoint: null,
    isLoading: false,
  }
  window.localStorage.clear()
})

describe('PushAlertsCard', () => {
  it('asks whose phone it is before offering to turn alerts on', () => {
    render(<PushAlertsCard />)

    expect(screen.getByText('Whose phone is this?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Elias' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mariana' })).toBeInTheDocument()
    // Nothing can be registered to nobody: the routing only works if the row
    // names a person.
    expect(
      screen.getByRole('button', { name: 'Turn on alerts for this phone' }),
    ).toBeDisabled()
  })

  it('says push is unconfigured rather than showing a button that can only fail', () => {
    subscriptionsState.data = list({ enabled: false, publicKey: '' })

    render(<PushAlertsCard />)

    expect(
      screen.getByText(/not configured on the server/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Turn on alerts for this phone' }),
    ).not.toBeInTheDocument()
  })

  it('tells a blocked phone where the fix is', () => {
    deviceState.current = { ...deviceState.current, permission: 'denied' }

    render(<PushAlertsCard />)

    expect(screen.getByText(/site settings/i)).toBeInTheDocument()
  })

  it('separates an insecure origin from an old browser', () => {
    // One is a deployment fact the household can fix; the other is not.
    deviceState.current = {
      ...deviceState.current,
      support: 'insecure-context',
    }

    render(<PushAlertsCard />)

    expect(screen.getByText(/secure connection/i)).toBeInTheDocument()
  })

  it('offers a test and an off switch once this phone is subscribed', () => {
    deviceState.current = {
      ...deviceState.current,
      permission: 'granted',
      endpoint: 'https://push.example/one',
    }

    render(<PushAlertsCard />)

    expect(screen.getByText('Alerts are on for this phone')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Send a test' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Turn off on this phone' }),
    ).toBeInTheDocument()
  })

  it('lists each registered phone by owner and model', () => {
    subscriptionsState.data = list({
      subscriptions: [
        {
          id: 'row-1',
          householdMemberId: 'member-1',
          memberName: 'Elias',
          deviceLabel: 'Pixel 7 Pro',
          createdAt: '2026-08-25T00:00:00+00:00',
          lastSuccessAt: '2026-08-25T00:00:00+00:00',
          lastFailureAt: null,
          lastError: null,
        },
        {
          id: 'row-2',
          householdMemberId: 'member-2',
          memberName: 'Mariana',
          deviceLabel: 'SM-S908U',
          createdAt: '2026-08-25T00:00:00+00:00',
          lastSuccessAt: null,
          lastFailureAt: null,
          lastError: null,
        },
      ],
    })

    render(<PushAlertsCard />)

    expect(screen.getByText('Elias — Pixel 7 Pro')).toBeInTheDocument()
    expect(screen.getByText('Mariana — SM-S908U')).toBeInTheDocument()
    // A phone that has never been pushed to reads as untested rather than fine.
    expect(screen.getByText('No alert sent yet')).toBeInTheDocument()
    expect(screen.getByText(/^Last alert /)).toBeInTheDocument()
  })

  it('marks the row this browser created as its own', () => {
    // The endpoint never comes back from the server, so the row id this device
    // stored is the only thing that can identify it.
    window.localStorage.setItem('portfolio-ai:push-subscription-id', 'row-1')
    subscriptionsState.data = list({
      subscriptions: [
        {
          id: 'row-1',
          householdMemberId: 'member-1',
          memberName: 'Elias',
          deviceLabel: 'Pixel 7 Pro',
          createdAt: null,
          lastSuccessAt: null,
          lastFailureAt: null,
          lastError: null,
        },
      ],
    })

    render(<PushAlertsCard />)

    expect(
      screen.getByText('Elias — Pixel 7 Pro (this phone)'),
    ).toBeInTheDocument()
  })

  it('surfaces the last send failure on the device it belongs to', () => {
    subscriptionsState.data = list({
      subscriptions: [
        {
          id: 'row-1',
          householdMemberId: 'member-2',
          memberName: 'Mariana',
          deviceLabel: 'SM-S908U',
          createdAt: null,
          lastSuccessAt: null,
          lastFailureAt: '2026-08-25T00:00:00+00:00',
          lastError: '503: push service unavailable',
        },
      ],
    })

    render(<PushAlertsCard />)

    expect(
      screen.getByText('503: push service unavailable'),
    ).toBeInTheDocument()
    expect(screen.getByText('Last send failed')).toBeInTheDocument()
  })
})
