import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import {
  calculateTickInterval,
  formatChartDate,
  TimeframeSelector,
  timeframeToDays,
} from '../TimeframeSelector'

describe('TimeframeSelector', () => {
  it('renders all timeframe buttons with the active one pressed', () => {
    render(<TimeframeSelector value="3M" onChange={vi.fn()} />)

    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(6)

    expect(screen.getByRole('button', { name: '3M' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: '1Y' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('calls onChange with the clicked timeframe value', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<TimeframeSelector value="1M" onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: '1Y' }))

    expect(onChange).toHaveBeenCalledWith('1Y')
  })
})

describe('timeframeToDays', () => {
  it('maps known timeframes to day counts', () => {
    expect(timeframeToDays('1M')).toBe(30)
    expect(timeframeToDays('3M')).toBe(90)
    expect(timeframeToDays('1Y')).toBe(365)
    expect(timeframeToDays('5Y')).toBe(1825)
  })
})

describe('formatChartDate', () => {
  it('uses short format for durations under 90 days', () => {
    const result = formatChartDate('2026-03-15', 30)
    expect(result).toMatch(/Mar\s+15/)
  })

  it('uses month-year format for durations over 90 days', () => {
    const result = formatChartDate('2026-03-15', 365)
    expect(result).toBe("Mar '26")
  })
})

describe('calculateTickInterval', () => {
  it('shows all ticks for short datasets', () => {
    expect(calculateTickInterval(20)).toBe(0)
  })

  it('targets 6-7 ticks for medium datasets', () => {
    const interval = calculateTickInterval(180)
    expect(interval).toBeGreaterThanOrEqual(25)
    expect(interval).toBeLessThanOrEqual(35)
  })

  it('targets ~7 ticks for large datasets', () => {
    const interval = calculateTickInterval(1000)
    expect(interval).toBeGreaterThanOrEqual(100)
    expect(interval).toBeLessThanOrEqual(200)
  })
})
