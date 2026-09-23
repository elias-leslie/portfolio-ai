import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FreshnessStatusBadge } from '../FreshnessStatusBadge'

const updatePreferences = vi.fn()

vi.mock('@/lib/hooks/useHealth', () => ({
  useLiveFreshness: () => ({
    data: { status: 'success', message: 'Market data is current' },
    refetch: vi.fn(),
  }),
  useRefreshAllFreshness: () => ({ isPending: false, mutate: vi.fn() }),
}))

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => ({ data: undefined }),
}))

vi.mock('@/lib/hooks/usePreferences', () => ({
  usePreferences: () => ({
    data: {
      frontendPollInterval: 30,
      scheduledAccountSyncEnabled: true,
    },
  }),
  useUpdatePreferences: () => ({
    mutate: updatePreferences,
    isPending: false,
    error: null,
  }),
}))

describe('FreshnessStatusBadge', () => {
  beforeEach(() => updatePreferences.mockClear())

  it('routes registered schedules to Agent Hub while keeping local controls', async () => {
    const user = userEvent.setup()
    render(<FreshnessStatusBadge />)

    await user.click(
      screen.getByRole('button', { name: 'Open data freshness feed' }),
    )

    expect(
      screen.getByRole('link', {
        name: 'Manage Portfolio automations in Agent Hub',
      }),
    ).toHaveAttribute(
      'href',
      'https://agent.summitflow.dev/automations?project_id=portfolio-ai',
    )
    expect(screen.queryByText('Jenny scheduled runs')).not.toBeInTheDocument()
    expect(screen.queryByText('ML labeling jobs')).not.toBeInTheDocument()
    expect(screen.queryByText('Strategy agents')).not.toBeInTheDocument()

    await user.click(
      screen.getByRole('switch', { name: 'Account syncs (SnapTrade, Plaid)' }),
    )
    expect(updatePreferences).toHaveBeenCalledWith({
      scheduledAccountSyncEnabled: false,
    })
  })
})
