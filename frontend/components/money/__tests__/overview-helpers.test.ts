import { describe, expect, it } from 'vitest'
import {
  allocationColors,
  formatMonthLabel,
  trendIncludesCurrentPartialMonth,
  trustBadgeVariant,
  trustStatusLabel,
} from '../overview-helpers'

describe('formatMonthLabel', () => {
  it('formats month keys in UTC so labels never shift a month west of Greenwich', () => {
    // '2026-05' parses as UTC midnight; local formatting in US timezones
    // would render it as April.
    expect(formatMonthLabel('2026-05')).toBe('May 26')
    expect(formatMonthLabel('2026-01')).toBe('Jan 26')
  })

  it('passes through unparseable values', () => {
    expect(formatMonthLabel('not-a-month')).toBe('not-a-month')
  })
})

describe('trendIncludesCurrentPartialMonth', () => {
  it('is true only when the latest trend month is the in-progress month', () => {
    const currentMonth = new Date().toLocaleDateString('en-CA').slice(0, 7)
    expect(
      trendIncludesCurrentPartialMonth([
        { month: '2026-01' },
        { month: currentMonth },
      ]),
    ).toBe(true)
    expect(
      trendIncludesCurrentPartialMonth([
        { month: '2026-01' },
        { month: '2026-02' },
      ]),
    ).toBe(false)
    expect(trendIncludesCurrentPartialMonth([])).toBe(false)
  })
})

describe('trustStatusLabel', () => {
  it('keeps a blocking state visible instead of down-toning it', () => {
    expect(trustStatusLabel('blocked')).toBe('Blocked')
  })

  it('still maps the normalized statuses', () => {
    expect(trustStatusLabel('trusted')).toBe('Current')
    expect(trustStatusLabel('partial')).toBe('Estimate')
    expect(trustStatusLabel('review')).toBe('Review')
    expect(trustStatusLabel('unavailable')).toBe('Unavailable')
  })
})

describe('trustBadgeVariant', () => {
  it('renders blocked as an error badge, not a muted outline', () => {
    expect(trustBadgeVariant('blocked')).toBe('error')
  })

  it('still maps the normalized statuses', () => {
    expect(trustBadgeVariant('trusted')).toBe('success')
    expect(trustBadgeVariant('partial')).toBe('warning')
    expect(trustBadgeVariant('review')).toBe('warning')
    expect(trustBadgeVariant('unavailable')).toBe('outline')
  })
})

describe('allocationColors', () => {
  it('skips through the ramp so adjacent donut slices stay distinguishable', () => {
    expect(allocationColors).toEqual([
      'var(--color-chart-1)',
      'var(--color-chart-3)',
      'var(--color-chart-5)',
      'var(--color-chart-2)',
      'var(--color-chart-4)',
    ])
  })
})
