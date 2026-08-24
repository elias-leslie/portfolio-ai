import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CapBar } from '../CapBar'

describe('CapBar', () => {
  it('draws nothing when no cap governs the category', () => {
    const { container } = render(
      <CapBar actual={500} cap={null} label="Household" />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('stops the fill at the cap so one breach cannot dwarf the rest', () => {
    render(<CapBar actual={3000} cap={1000} label="Household" />)

    const bar = screen.getByRole('img', { name: 'Household: 300% of cap' })
    const fill = bar.firstElementChild as HTMLElement

    expect(fill.style.width).toBe('100%')
  })

  it('reads an under-budget category as a distance from the mark', () => {
    render(<CapBar actual={250} cap={1000} label="Groceries" />)

    const bar = screen.getByRole('img', { name: 'Groceries: 25% of cap' })
    const fill = bar.firstElementChild as HTMLElement

    expect(fill.style.width).toBe('25%')
  })
})
