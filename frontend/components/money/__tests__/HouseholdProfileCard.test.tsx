import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HouseholdProfileCard } from '../HouseholdProfileCard'

const mutate = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUpdateHouseholdProfile: () => ({
    mutate,
    isPending: false,
  }),
}))

describe('HouseholdProfileCard', () => {
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
      />,
    )

    fireEvent.change(screen.getByLabelText(/household name/i), {
      target: { value: 'Kasadis Family' },
    })
    fireEvent.change(screen.getByLabelText(/monthly take-home income/i), {
      target: { value: '12500' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save plan/i }))

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({
        householdName: 'Kasadis Family',
        monthlyNetIncomeTarget: 12500,
      }),
    )
  })
})
