import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WatchlistSearchBar } from '../WatchlistSearchBar'

describe('WatchlistSearchBar', () => {
  it('uses scanner signal language without thesis or live-model clutter', () => {
    render(
      <WatchlistSearchBar
        value=""
        onChange={vi.fn()}
        resultCount={4}
        totalCount={4}
      />,
    )

    expect(
      screen.getByPlaceholderText(/search symbol or signal context/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/search symbol, signal context, risk, or style/i),
    ).toBeInTheDocument()
  })
})
