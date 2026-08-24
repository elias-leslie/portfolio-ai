import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HouseholdNoveltyCluster } from '@/lib/api/household'
import { NewThisMonthCard } from '../NewThisMonthCard'

const trip: HouseholdNoveltyCluster = {
  key: '2026-07-02:23',
  label: '23 new places, 2-13 July',
  detail: 'None of them charged the household in the 6 months on record.',
  startDate: '2026-07-02',
  endDate: '2026-07-13',
  total: 1233.33,
  merchantCount: 23,
  transactionCount: 31,
  isCluster: true,
  merchants: [
    {
      merchant: 'Memos Cabanas',
      category: 'Dining',
      amount: 32,
      transactionCount: 1,
      firstSeen: '2026-07-03',
    },
    {
      merchant: 'Discover Coatepeque',
      category: 'Travel',
      amount: 65,
      transactionCount: 1,
      firstSeen: '2026-07-10',
    },
  ],
}

const loner: HouseholdNoveltyCluster = {
  key: '2026-07-16:Hsr K',
  label: 'Hsr K',
  detail:
    'First charge from this merchant in the 6 months on record · Insurance.',
  startDate: '2026-07-16',
  endDate: '2026-07-16',
  total: 6.75,
  merchantCount: 1,
  transactionCount: 2,
  isCluster: false,
  merchants: [
    {
      merchant: 'Hsr K',
      category: 'Insurance',
      amount: 6.75,
      transactionCount: 2,
      firstSeen: '2026-07-16',
    },
  ],
}

describe('NewThisMonthCard', () => {
  it('reads as outings rather than a list of unfamiliar names', () => {
    render(<NewThisMonthCard clusters={[trip, loner]} monthLabel="July 2026" />)

    expect(screen.getByText('23 new places, 2-13 July')).toBeInTheDocument()
    expect(screen.getByText('$1,233')).toBeInTheDocument()
  })

  it('counts every new merchant in the header, clustered or not', () => {
    render(<NewThisMonthCard clusters={[trip, loner]} monthLabel="July 2026" />)

    expect(
      screen.getByText(
        '24 merchants with no history before July 2026, $1,240 in total.',
      ),
    ).toBeInTheDocument()
  })

  it('opens a cluster to the merchants inside it', () => {
    render(<NewThisMonthCard clusters={[trip]} monthLabel="July 2026" />)

    expect(screen.queryByText('Memos Cabanas')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { expanded: false }))

    expect(screen.getByText('Memos Cabanas')).toBeInTheDocument()
    expect(screen.getByText('Discover Coatepeque')).toBeInTheDocument()
  })

  it('shows a lone new merchant under its own name', () => {
    render(<NewThisMonthCard clusters={[loner]} monthLabel="July 2026" />)

    expect(screen.getByText('Hsr K')).toBeInTheDocument()
    expect(screen.getByText('$7')).toBeInTheDocument()
  })

  it('renders nothing in a month that broke no new ground', () => {
    const { container } = render(
      <NewThisMonthCard clusters={[]} monthLabel="July 2026" />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
