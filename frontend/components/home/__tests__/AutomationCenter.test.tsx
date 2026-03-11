import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AutomationCenter } from '../AutomationCenter'

const updatePreferencesMutate = vi.fn()
const useAutomationCenterMock = vi.fn()

vi.mock('@/lib/hooks/useHomeActionQueue', () => ({
  useAutomationCenter: () => useAutomationCenterMock(),
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useRunJennyRoutine: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}))

vi.mock('@/lib/hooks/usePreferences', () => ({
  useUpdatePreferences: () => ({
    mutate: updatePreferencesMutate,
    isPending: false,
  }),
}))

describe('AutomationCenter', () => {
  beforeEach(() => {
    updatePreferencesMutate.mockReset()
    useAutomationCenterMock.mockReturnValue({
      data: {
        guardrails: [
          {
            key: 'thesis_generation_enabled',
            label: 'Thesis generation',
            value: 'Disabled',
            enabled: false,
            source: 'rules_default',
            detail: 'Controls whether Jenny can auto-generate missing theses.',
          },
        ],
        recentRuns: [],
        warnings: [],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
  })

  it('updates runtime automation preferences from the toggle', async () => {
    const user = userEvent.setup()

    render(<AutomationCenter />)

    await user.click(screen.getByRole('switch', { name: /toggle thesis generation/i }))

    expect(updatePreferencesMutate).toHaveBeenCalledWith({
      thesisGenerationEnabled: true,
    })
  })

  it('shows Running for active routines without a completed timestamp', () => {
    useAutomationCenterMock.mockReturnValue({
      data: {
        guardrails: [],
        recentRuns: [
          {
            id: 'routine-1',
            label: 'Jenny daily operator',
            status: 'running',
            triggeredBy: 'scheduled',
            startedAt: '2026-03-10T14:00:00+00:00',
            completedAt: null,
            detail: 'Reviewing 7 symbols.',
          },
        ],
        warnings: ['monitor thesis health reported failed.'],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<AutomationCenter />)

    expect(screen.getByText('Jenny daily operator')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
    expect(screen.getByText('monitor thesis health reported failed.')).toBeInTheDocument()
  })

  it('offers retry when the automation query fails', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    useAutomationCenterMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('unavailable'),
      refetch,
    })

    render(<AutomationCenter />)

    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(refetch).toHaveBeenCalled()
  })
})
