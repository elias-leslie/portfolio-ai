import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WatchlistFilterBar } from '../WatchlistFilterBar'

describe('WatchlistFilterBar', () => {
  it('labels raw signal filters as scanner setups', () => {
    render(
      <WatchlistFilterBar
        totalCount={7}
        signalFilter="all"
        onSignalChange={vi.fn()}
        styleFilter="all"
        onStyleChange={vi.fn()}
        riskFilter="all"
        onRiskChange={vi.fn()}
        counts={{
          style: {},
          signal: { BUY: 2, HOLD: 3, AVOID: 1 },
          risk: {},
        }}
        hasActiveFilters={false}
        onReset={vi.fn()}
      />,
    )

    expect(
      screen.getByRole('combobox', { name: /filter by setup/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/all setups/i)).toBeInTheDocument()
  })
})
