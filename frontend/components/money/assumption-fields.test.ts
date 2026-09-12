import { describe, expect, it } from 'vitest'
import {
  assumptionField,
  formatAssumptionValue,
  parseStoredAssumption,
} from './assumption-fields'

describe('household assumption units', () => {
  it.each([
    ['target_spouse_retirement_age', '49', 'Age 49'],
    ['retirement_horizon_years', '35', '35 years'],
    ['retirement_inflation_rate', '0.026', '2.6%'],
    ['social_security_payable_ratio', '0.77', '77%'],
    ['effective_tax_rate', '24', '24%'],
    ['effective_tax_rate', 'unknown', 'Not established'],
    ['filing_status', 'married_filing_jointly', 'Married filing jointly'],
  ])('renders %s consistently for stored and found values', (field, raw, expected) => {
    const def = assumptionField(field)
    expect(def).toBeDefined()
    if (!def) return
    expect(formatAssumptionValue(def, raw)).toBe(expected)
  })
  it('cannot turn unknown, invalid fractions, or fractional ages into accepted inputs', () => {
    for (const [field, raw] of [
      ['effective_tax_rate', 'unknown'],
      ['social_security_payable_ratio', '77'],
      ['target_retirement_age', '59.5'],
      ['monthly_savings_target', 'Infinity'],
      ['retirement_horizon_years', '0'],
    ]) {
      const def = assumptionField(field)
      if (!def) throw new Error(field)
      expect(parseStoredAssumption(def, raw)).toBeNull()
    }
  })
})
