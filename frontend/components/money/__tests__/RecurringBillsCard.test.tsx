'use client'

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HouseholdRecurringCommitment } from '@/lib/api/household'
import { RecurringBillsCard } from '../RecurringBillsCard'

function commitment(
  overrides: Partial<HouseholdRecurringCommitment>,
): HouseholdRecurringCommitment {
  return {
    merchant: 'Duke Energy',
    category: 'Bills',
    cadence: 'likely monthly',
    averageAmount: 184.05,
    annualizedCost: 2208.6,
    lastSeen: '2026-08-10',
    nextExpected: '2026-09-10',
    daysUntilDue: 18,
    dueStatus: 'upcoming',
    dueConfidence: 0.95,
    commitmentType: 'bill',
    evidence:
      '8 charges across 8 months, about 30 days apart, typically 184.05.',
    ...overrides,
  }
}

describe('RecurringBillsCard', () => {
  it('shows the evidence behind each commitment', () => {
    // "Recurring" was previously a claim with nothing behind it: two sightings
    // and the largest average won. The card now carries the count, the span and
    // the gap, so the reader can check the claim instead of trusting it.
    render(<RecurringBillsCard dueSoonCommitments={[commitment({})]} />)

    expect(screen.getByText('Duke Energy')).toBeInTheDocument()
    expect(
      screen.getByText(
        '8 charges across 8 months, about 30 days apart, typically 184.05.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Expected in 18 days.')).toBeInTheDocument()
  })

  it('says a late bill is late rather than counting the days forward', () => {
    render(
      <RecurringBillsCard
        dueSoonCommitments={[
          commitment({
            merchant: 'YouTube Premium',
            commitmentType: 'subscription',
            daysUntilDue: -26,
            dueStatus: 'overdue',
          }),
        ]}
      />,
    )

    expect(screen.getByText('Expected 26 days ago.')).toBeInTheDocument()
  })

  it('renders without evidence when the cadence was declared, not inferred', () => {
    render(
      <RecurringBillsCard
        dueSoonCommitments={[
          commitment({ merchant: 'Harbor Hills Property', evidence: null }),
        ]}
      />,
    )

    expect(screen.getByText('Harbor Hills Property')).toBeInTheDocument()
  })
})
