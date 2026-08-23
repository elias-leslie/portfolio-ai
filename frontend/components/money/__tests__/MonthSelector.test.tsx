import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MonthSelector } from '../MonthSelector'

const months = ['2026-05', '2026-06', '2026-07', '2026-08']

describe('MonthSelector', () => {
  it('steps back one calendar month at a time', () => {
    const onChange = vi.fn()
    render(
      <MonthSelector
        availableMonths={months}
        month="2026-07"
        onChange={onChange}
      />,
    )

    fireEvent.click(screen.getByLabelText('Previous month'))

    expect(onChange).toHaveBeenCalledWith('2026-06')
  })

  it('steps forward one calendar month at a time', () => {
    const onChange = vi.fn()
    render(
      <MonthSelector
        availableMonths={months}
        month="2026-07"
        onChange={onChange}
      />,
    )

    fireEvent.click(screen.getByLabelText('Next month'))

    expect(onChange).toHaveBeenCalledWith('2026-08')
  })

  it('cannot walk off either end of the ledger', () => {
    const { rerender } = render(
      <MonthSelector
        availableMonths={months}
        month="2026-05"
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByLabelText('Previous month')).toBeDisabled()

    rerender(
      <MonthSelector
        availableMonths={months}
        month="2026-08"
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByLabelText('Next month')).toBeDisabled()
  })

  it('says so when the month on screen has not finished yet', () => {
    render(
      <MonthSelector
        availableMonths={months}
        month="2026-08"
        onChange={vi.fn()}
        isMonthToDate
        basisLabel="through day 23 of 31"
      />,
    )

    expect(
      screen.getByText('Month to date · through day 23 of 31'),
    ).toBeInTheDocument()
  })

  it('stays quiet about pacing on a month that has closed', () => {
    render(
      <MonthSelector
        availableMonths={months}
        month="2026-07"
        onChange={vi.fn()}
      />,
    )

    expect(screen.queryByText(/Month to date/)).not.toBeInTheDocument()
  })
})
