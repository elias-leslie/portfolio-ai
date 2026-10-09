import { describe, expect, it } from 'vitest'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatInteger,
  formatPercent,
  formatPnlDollars,
  formatThousandsAxis,
} from './formatters'

describe('formatCurrency', () => {
  it('uses the null placeholder for NaN and Infinity', () => {
    expect(formatCurrency(Number.NaN)).toBe('—')
    expect(formatCurrency(Number.POSITIVE_INFINITY)).toBe('—')
    expect(
      formatCurrency(Number.NEGATIVE_INFINITY, { nullDisplay: 'n/a' }),
    ).toBe('n/a')
    expect(formatInteger(Number.NaN)).toBe('—')
    expect(formatPercent(Number.NaN)).toBe('—')
  })

  it('never renders negative zero', () => {
    expect(formatCurrency(-0)).toBe('$0.00')
    expect(formatCurrency(-0.004)).toBe('$0.00')
    expect(formatCurrencyWhole(-0.4)).toBe('$0')
    expect(formatPercent(-0.04, { sign: true })).toBe('+0.0%')
  })

  it('keeps negatives and pinned en-US grouping', () => {
    expect(formatCurrency(-1234.5)).toBe('-$1,234.50')
    expect(formatCurrency(1234.5, { currency: 'EUR' })).toBe('€1,234.50')
  })

  it('falls back to a code-prefixed number for invalid currency codes', () => {
    expect(formatCurrency(1234.5, { currency: 'NOT-A-CODE' })).toBe(
      'NOT-A-CODE 1,234.50',
    )
  })
})

describe('formatPnlDollars', () => {
  it('signs values with the same en-US formatting as formatCurrency', () => {
    expect(formatPnlDollars(1234.5)).toBe('+$1,234.50')
    expect(formatPnlDollars(-1234.5)).toBe('-$1,234.50')
    expect(formatPnlDollars(-0.001)).toBe('+$0.00')
    expect(formatPnlDollars(Number.NaN)).toBe('—')
  })
})

describe('formatThousandsAxis', () => {
  it('renders compact ticks with the sign before the dollar sign', () => {
    expect(formatThousandsAxis(0)).toBe('$0')
    expect(formatThousandsAxis(-0.2)).toBe('$0')
    expect(formatThousandsAxis(500)).toBe('$500')
    expect(formatThousandsAxis(-500)).toBe('-$500')
    expect(formatThousandsAxis(2000)).toBe('$2k')
    expect(formatThousandsAxis(-1500)).toBe('-$1.5k')
    expect(formatThousandsAxis(Number.NaN)).toBe('—')
  })
})
