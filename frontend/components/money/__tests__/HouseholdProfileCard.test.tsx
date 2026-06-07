import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HouseholdProfileCard } from '../HouseholdProfileCard'

const mutate = vi.fn()
const useUpdateHouseholdProfileMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUpdateHouseholdProfile: () =>
    useUpdateHouseholdProfileMock() ?? {
      mutate,
      isPending: false,
    },
}))

describe('HouseholdProfileCard', () => {
  beforeEach(() => {
    useUpdateHouseholdProfileMock.mockReset()
    mutate.mockReset()
  })

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
      />,
    )

    fireEvent.change(screen.getByLabelText(/household name/i), {
      target: { value: 'Demo Family' },
    })
    fireEvent.change(screen.getByLabelText(/monthly take-home income/i), {
      target: { value: '12500' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save overrides/i }))

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({
        householdName: 'Demo Family',
        monthlyNetIncomeTarget: 12500,
      }),
    )
  })

  it('shows an empty state when Jenny has not resolved any planning values yet', () => {
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
      />,
    )

    expect(
      screen.getByText(
        /jenny has not resolved any structured planning values yet/i,
      ),
    ).toBeInTheDocument()
  })

  it('marks the save action busy while overrides are saving', () => {
    useUpdateHouseholdProfileMock.mockReturnValue({
      mutate,
      isPending: true,
    })

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
      />,
    )

    expect(screen.getByRole('button', { name: /saving/i })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })
})
