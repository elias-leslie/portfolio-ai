import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ThesisSection } from '../ThesisSection'

const useQueryMock = vi.fn()
const useMutationMock = vi.fn()
const invalidateQueries = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (...args: unknown[]) => useQueryMock(...args),
  useMutation: (...args: unknown[]) => useMutationMock(...args),
  useQueryClient: () => ({
    invalidateQueries,
  }),
}))

vi.mock('../thesis/ActionBadge', () => ({
  ActionBadge: () => <div>Action Badge</div>,
}))
vi.mock('../thesis/ClaudeValidationSection', () => ({
  ClaudeValidationSection: () => <div>Claude Validation</div>,
}))
vi.mock('../thesis/CoreReasonsSection', () => ({
  CoreReasonsSection: () => <div>Core Reasons</div>,
}))
vi.mock('../thesis/ExpectedReturnsSection', () => ({
  ExpectedReturnsSection: () => <div>Expected Returns</div>,
}))
vi.mock('../thesis/KeyCatalystsSection', () => ({
  KeyCatalystsSection: () => <div>Key Catalysts</div>,
}))
vi.mock('../thesis/RisksSection', () => ({
  RisksSection: () => <div>Risks</div>,
}))
vi.mock('../thesis/StatusBadge', () => ({
  StatusBadge: () => <div>Status Badge</div>,
}))
vi.mock('../thesis/ValueDriversSection', () => ({
  ValueDriversSection: () => <div>Value Drivers</div>,
}))
vi.mock('../thesis/VersionHistorySection', () => ({
  VersionHistorySection: () => <div>Version History</div>,
}))

describe('ThesisSection', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    useMutationMock.mockReset()
    invalidateQueries.mockReset()
  })

  it('marks the generate action busy while a thesis is being created', () => {
    useQueryMock.mockReturnValue({
      data: { thesis: null, versions: [] },
      isLoading: false,
      error: null,
    })
    useMutationMock
      .mockReturnValueOnce({
        mutate: vi.fn(),
        isPending: true,
      })
      .mockReturnValueOnce({
        mutate: vi.fn(),
        isPending: false,
      })

    render(<ThesisSection symbol="MSFT" userTimezone="America/New_York" />)

    expect(screen.getByRole('button', { name: /generating/i })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })

  it('marks regenerate and invalidate actions busy while thesis mutations are running', async () => {
    useQueryMock.mockReturnValue({
      data: {
        thesis: {
          action: 'BUY',
          crossValidationScore: null,
          status: 'active',
          coreReasons: [],
          keyCatalysts: [],
          risks: [],
          valueDrivers: null,
          expectedReturnPct: null,
          expectedTimeframeDays: null,
          claudeValidation: null,
          version: 2,
          updatedAt: '2026-03-11T00:00:00Z',
        },
        versions: [],
      },
      isLoading: false,
      error: null,
    })
    useMutationMock.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
    })
    const user = userEvent.setup()

    render(<ThesisSection symbol="MSFT" userTimezone="America/New_York" />)

    await user.click(screen.getByRole('button', { name: /admin/i }))

    expect(
      screen.getByRole('button', { name: /regenerating/i }),
    ).toHaveAttribute('aria-busy', 'true')
    expect(
      screen.getByRole('button', { name: /invalidating/i }),
    ).toHaveAttribute('aria-busy', 'true')
  })
})
