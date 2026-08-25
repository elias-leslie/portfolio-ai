'use client'

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ItemLinkageCard } from '../ItemLinkageCard'

const usePurchaseItemLinkageMock = vi.hoisted(() => vi.fn())

vi.mock('@/lib/hooks/useHouseholdPurchases', () => ({
  usePurchaseItemLinkage: usePurchaseItemLinkageMock,
}))

const coverage = {
  generatedAt: '2026-08-25T12:00:00Z',
  totalItems: 3128,
  linkedItems: 121,
  addressableItems: 295,
  addressableLinkedShare: 0.4102,
  feedStartsOn: '2025-12-24',
  buckets: [
    {
      state: 'linked',
      label: 'Tied to a charge',
      detail: 'the item and the money are the same event',
      itemCount: 121,
      amount: 2941.24,
    },
    {
      state: 'before_feed',
      label: 'Older than the feed',
      detail: "bought on a known card before that account's feed begins",
      itemCount: 2069,
      amount: 86566.68,
    },
  ],
  unknownCards: [
    {
      mask: '4000',
      itemCount: 274,
      amount: 13226.69,
      firstSeen: '2011-02-16',
      lastSeen: '2014-08-05',
    },
  ],
}

describe('ItemLinkageCard', () => {
  it('reports the share over items whose charge could exist, not over every item ever imported', () => {
    usePurchaseItemLinkageMock.mockReturnValue({
      data: coverage,
      isLoading: false,
      error: null,
    })
    render(<ItemLinkageCard />)
    expect(screen.getByText(/121 of 295/)).toBeInTheDocument()
    expect(screen.queryByText(/of 3,128/)).not.toBeInTheDocument()
  })

  it('says how many items are outside what the household has connected', () => {
    usePurchaseItemLinkageMock.mockReturnValue({
      data: coverage,
      isLoading: false,
      error: null,
    })
    render(<ItemLinkageCard />)
    expect(
      screen.getByText(/A further 2,833 were bought outside/),
    ).toBeInTheDocument()
    expect(screen.getByText(/oldest charge we hold/)).toBeInTheDocument()
  })

  it('names a card no account claims, with the window it was used in', () => {
    usePurchaseItemLinkageMock.mockReturnValue({
      data: coverage,
      isLoading: false,
      error: null,
    })
    render(<ItemLinkageCard />)
    expect(screen.getByText('···4000')).toBeInTheDocument()
    expect(screen.getByText(/274 items/)).toBeInTheDocument()
  })

  it('states no share at all when nothing is addressable', () => {
    usePurchaseItemLinkageMock.mockReturnValue({
      data: {
        ...coverage,
        linkedItems: 0,
        addressableItems: 0,
        addressableLinkedShare: null,
      },
      isLoading: false,
      error: null,
    })
    render(<ItemLinkageCard />)
    expect(screen.getByText(/0 of 0/)).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })
})
