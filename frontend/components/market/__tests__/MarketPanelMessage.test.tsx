import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MarketPanelMessage } from '../MarketPanelMessage'

describe('MarketPanelMessage', () => {
  it('renders the message with status role', () => {
    render(<MarketPanelMessage message="Market data temporarily unavailable" />)

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('Market data temporarily unavailable')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    render(<MarketPanelMessage message="Test" className="mt-4" />)

    expect(screen.getByRole('status').className).toContain('mt-4')
  })
})
