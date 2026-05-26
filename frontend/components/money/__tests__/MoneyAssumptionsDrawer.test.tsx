'use client'

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { HouseholdProfile } from '@/lib/api/household'
import {
  useConfirmFact,
  useUpdateHouseholdProfile,
} from '@/lib/hooks/useHousehold'
import { MoneyAssumptionsDrawer } from '../MoneyAssumptionsDrawer'

vi.mock('@/lib/hooks/useHousehold', () => ({
  useConfirmFact: vi.fn(),
  useUpdateHouseholdProfile: vi.fn(),
}))

const updateProfileMutateAsync = vi.fn()
const confirmFactMutateAsync = vi.fn()
const useUpdateProfileMock = vi.mocked(useUpdateHouseholdProfile)
const useConfirmFactMock = vi.mocked(useConfirmFact)

const profile: HouseholdProfile = {
  id: 'profile-1',
  householdName: 'Household',
  adultCount: 2,
  dependentCount: 0,
  monthlyNetIncomeTarget: 10000,
  monthlyEssentialTarget: 5000,
  monthlyDiscretionaryTarget: 2000,
  monthlySavingsTarget: 1500,
  targetRetirementAge: 65,
  targetRetirementSpend: 6000,
  retirementInflationRate: 0.025,
  retirementHorizonYears: 35,
  primarySocialSecurityMonthly: null,
  spouseSocialSecurityMonthly: null,
  primarySocialSecurityAnnualEarnings: 120000,
  spouseSocialSecurityAnnualEarnings: 85000,
  primarySocialSecurityStartAge: 67,
  spouseSocialSecurityStartAge: 67,
  filingStatus: 'Married filing jointly',
  stateOfResidence: 'FL',
  effectiveTaxRate: 18,
  marginalFederalTaxRate: 22,
  marginalStateTaxRate: 0,
  emergencyFundTargetMonths: 6,
  emergencyFundTargetAmount: 50000,
  notes: null,
  createdAt: '2026-05-26T00:00:00Z',
  updatedAt: '2026-05-26T00:00:00Z',
}

describe('MoneyAssumptionsDrawer', () => {
  beforeEach(() => {
    updateProfileMutateAsync.mockReset()
    confirmFactMutateAsync.mockReset()
    updateProfileMutateAsync.mockResolvedValue(profile)
    confirmFactMutateAsync.mockResolvedValue({})
    useUpdateProfileMock.mockReturnValue({
      mutateAsync: updateProfileMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateHouseholdProfile>)
    useConfirmFactMock.mockReturnValue({
      mutateAsync: confirmFactMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useConfirmFact>)
  })

  it('saves multiple edited assumption values at once and accepts formatted numbers', async () => {
    const user = userEvent.setup()
    render(
      <MoneyAssumptionsDrawer
        profile={profile}
        resolvedValues={[]}
        facts={[]}
      />,
    )

    const retirementSpendRow = screen
      .getByText('Retirement monthly spend')
      .closest('tr')
    const inflationRow = screen
      .getByText('Retirement inflation rate')
      .closest('tr')
    const salaryRow = screen
      .getByText('Your Social Security salary')
      .closest('tr')

    expect(retirementSpendRow).not.toBeNull()
    expect(inflationRow).not.toBeNull()
    expect(salaryRow).not.toBeNull()

    const retirementSpendInput = within(retirementSpendRow!).getByDisplayValue(
      '6000',
    )
    await user.clear(retirementSpendInput)
    await user.type(retirementSpendInput, '$7,500')

    const inflationInput = within(inflationRow!).getByDisplayValue('2.5')
    await user.clear(inflationInput)
    await user.type(inflationInput, '3%')

    const salaryInput = within(salaryRow!).getByDisplayValue('120000')
    await user.clear(salaryInput)
    await user.type(salaryInput, '125,000')

    await user.click(screen.getByRole('button', { name: /save all changes/i }))

    expect(updateProfileMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        targetRetirementSpend: 7500,
        retirementInflationRate: 0.03,
        primarySocialSecurityAnnualEarnings: 125000,
      }),
    )
  })
})
