import { describe, expect, it } from 'vitest'
import type { HouseholdAccountSummary } from '@/lib/api/household'
import { accountMetaLine, freshnessBadgeVariant } from '../moneyAccountsUtils'

function buildAccount(
  overrides: Partial<HouseholdAccountSummary>,
): HouseholdAccountSummary {
  return {
    assetGroup: 'cash',
    accountType: 'checking',
    institutionName: null,
    ownerName: null,
    ...overrides,
  } as HouseholdAccountSummary
}

describe('accountMetaLine', () => {
  it('humanizes underscored account-type slugs', () => {
    expect(
      accountMetaLine(
        buildAccount({
          assetGroup: 'retirement',
          accountType: 'roth_403b',
          institutionName: 'Fidelity',
          ownerName: 'Sam',
        }),
      ),
    ).toBe('retirement · roth 403b · Fidelity · Sam')
    expect(
      accountMetaLine(
        buildAccount({
          assetGroup: 'retirement',
          accountType: 'governmental_457b',
        }),
      ),
    ).toBe('retirement · governmental 457b')
  })

  it('skips the account type when it just repeats the asset group', () => {
    expect(
      accountMetaLine(
        buildAccount({
          assetGroup: 'retirement',
          accountType: 'retirement',
          institutionName: 'Vanguard',
        }),
      ),
    ).toBe('retirement · Vanguard')
  })

  it('keeps distinct types and optional segments intact', () => {
    expect(
      accountMetaLine(
        buildAccount({
          assetGroup: 'cash',
          accountType: 'checking',
          institutionName: 'Wells Fargo',
        }),
      ),
    ).toBe('cash · checking · Wells Fargo')
  })
})

describe('freshnessBadgeVariant', () => {
  it('maps freshness tones to the shared badge variants', () => {
    expect(freshnessBadgeVariant('fresh')).toBe('success')
    expect(freshnessBadgeVariant('aging')).toBe('warning')
    expect(freshnessBadgeVariant('stale')).toBe('error')
    expect(freshnessBadgeVariant('not_applicable')).toBe('outline')
    expect(freshnessBadgeVariant('needs_evidence')).toBe('default')
    expect(freshnessBadgeVariant(undefined)).toBe('default')
  })
})
