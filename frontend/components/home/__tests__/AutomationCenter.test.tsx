import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AutomationCenter } from '../AutomationCenter'

const updatePreferencesMutate = vi.fn()

vi.mock('@/lib/hooks/useHomeActionQueue', () => ({
  useAutomationCenter: () => ({
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
    error: null,
  }),
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
  it('updates runtime automation preferences from the toggle', async () => {
    const user = userEvent.setup()

    render(<AutomationCenter />)

    await user.click(screen.getByRole('switch', { name: /toggle thesis generation/i }))

    expect(updatePreferencesMutate).toHaveBeenCalledWith({
      thesisGenerationEnabled: true,
    })
  })
})
