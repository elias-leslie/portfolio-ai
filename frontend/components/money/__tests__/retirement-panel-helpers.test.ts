import { describe, expect, it } from 'vitest'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { householdAges, memberAge, percentInput } from '../MoneyRetirementPanel'

type Member = NonNullable<
  HouseholdFinanceDashboard['planning']
>['members'][number]

function member(overrides: Partial<Member>): Member {
  return {
    id: 'member-1',
    displayName: 'Member',
    role: 'adult',
    relationship: null,
    birthYear: 1980,
    isDependent: false,
    livesInHousehold: true,
    notes: null,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Member
}

// Midday UTC in June keeps the local calendar date stable in any timezone.
const generatedAt = '2026-06-15T12:00:00Z'
const asOf = new Date(2026, 5, 15)

function dashboardWith(members: Member[] | undefined) {
  return {
    generatedAt,
    planning: members ? { members } : undefined,
  } as unknown as HouseholdFinanceDashboard
}

describe('percentInput', () => {
  it('falls back to 2.5 for null and undefined (callers rely on it)', () => {
    expect(percentInput(null)).toBe('2.5')
    expect(percentInput(undefined)).toBe('2.5')
  })

  it('honors an explicit fallback', () => {
    expect(percentInput(null, '5')).toBe('5')
  })

  it('renders 0 as 0, not the fallback', () => {
    expect(percentInput(0)).toBe('0')
  })

  it('rounds to one decimal place', () => {
    expect(percentInput(0.0333)).toBe('3.3')
  })

  it('cancels float noise (0.07 * 1000 = 70.000…01)', () => {
    expect(percentInput(0.07)).toBe('7')
  })

  it('rounds 0.05% up and 0.049% down', () => {
    expect(percentInput(0.0005)).toBe('0.1')
    expect(percentInput(0.00049)).toBe('0')
  })

  it('passes negatives through', () => {
    expect(percentInput(-0.01)).toBe('-1')
  })
})

describe('memberAge', () => {
  it('returns null without a birth year (null, undefined, or 0)', () => {
    expect(memberAge(member({ birthYear: null }), asOf)).toBeNull()
    expect(memberAge(member({ birthYear: undefined }), asOf)).toBeNull()
    expect(memberAge(member({ birthYear: 0 }), asOf)).toBeNull()
  })

  it('uses the plain year difference without a DOB note', () => {
    expect(memberAge(member({ birthYear: 1980 }), asOf)).toBe(46)
  })

  it('subtracts a year before the birthday in a dob: note', () => {
    expect(
      memberAge(member({ birthYear: 1980, notes: 'dob: 1980-12-25' }), asOf),
    ).toBe(45)
  })

  it('keeps the year difference after the birthday (single-digit M-D)', () => {
    expect(
      memberAge(member({ birthYear: 1980, notes: 'DOB: 1980-3-2' }), asOf),
    ).toBe(46)
  })

  it('clamps a future birth year to 0', () => {
    expect(memberAge(member({ birthYear: 2030 }), asOf)).toBe(0)
  })

  it('is safe when notes is null', () => {
    expect(memberAge(member({ birthYear: 1990, notes: null }), asOf)).toBe(36)
  })
})

describe('householdAges', () => {
  it('returns nulls when planning is undefined', () => {
    expect(householdAges(dashboardWith(undefined))).toEqual({
      primaryAge: null,
      spouseAge: null,
    })
  })

  it('finds primary and spouse by role', () => {
    const ages = householdAges(
      dashboardWith([
        member({ id: 'p', role: 'self', birthYear: 1976 }),
        member({ id: 's', role: 'partner', birthYear: 1981 }),
      ]),
    )
    expect(ages).toEqual({ primaryAge: 50, spouseAge: 45 })
  })

  it('matches roles case-insensitively', () => {
    const ages = householdAges(
      dashboardWith([
        member({ id: 'p', role: 'OWNER', birthYear: 1976 }),
        member({ id: 's', role: 'Spouse', birthYear: 1981 }),
      ]),
    )
    expect(ages).toEqual({ primaryAge: 50, spouseAge: 45 })
  })

  it('falls back to relationships when roles do not match', () => {
    const ages = householdAges(
      dashboardWith([
        member({
          id: 'p',
          role: 'adult',
          relationship: 'husband',
          birthYear: 1976,
        }),
        member({
          id: 's',
          role: 'adult',
          relationship: 'wife',
          birthYear: 1981,
        }),
      ]),
    )
    expect(ages).toEqual({ primaryAge: 50, spouseAge: 45 })
    const parentAges = householdAges(
      dashboardWith([
        member({
          id: 'p',
          role: 'adult',
          relationship: 'Father',
          birthYear: 1976,
        }),
        member({
          id: 's',
          role: 'adult',
          relationship: 'Mother',
          birthYear: 1981,
        }),
      ]),
    )
    expect(parentAges).toEqual({ primaryAge: 50, spouseAge: 45 })
  })

  it('excludes dependents by flag, role, and relationship', () => {
    const ages = householdAges(
      dashboardWith([
        member({ id: 'p', role: 'self', birthYear: 1976 }),
        member({
          id: 'dep-flag',
          role: 'self',
          birthYear: 2010,
          isDependent: true,
        }),
        member({ id: 'dep-role', role: 'child', birthYear: 2010 }),
        member({
          id: 'dep-rel',
          role: 'spouse',
          relationship: 'daughter',
          birthYear: 2012,
        }),
      ]),
    )
    expect(ages).toEqual({ primaryAge: 50, spouseAge: null })
  })

  it('returns null for a matched member without a birth year', () => {
    const ages = householdAges(
      dashboardWith([
        member({ id: 'p', role: 'self', birthYear: null }),
        member({ id: 's', role: 'spouse', birthYear: 1981 }),
      ]),
    )
    expect(ages).toEqual({ primaryAge: null, spouseAge: 45 })
  })
})
