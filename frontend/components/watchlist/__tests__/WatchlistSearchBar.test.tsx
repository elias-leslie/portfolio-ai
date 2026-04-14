import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WatchlistSearchBar } from '../WatchlistSearchBar'

describe('WatchlistSearchBar', () => {
  it('uses live setup language instead of ambiguous signal copy', () => {
    render(
      <WatchlistSearchBar
        value=""
        onChange={vi.fn()}
        resultCount={4}
        totalCount={4}
      />,
    )

    expect(
      screen.getByPlaceholderText(
        /search symbol, note, thesis, or live setup/i,
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/search symbol, note, thesis headline, or live setup/i),
    ).toBeInTheDocument()
  })
})
