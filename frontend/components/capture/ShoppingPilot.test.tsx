import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { parseComparison, parseReview } from '@/lib/shopping-pilot'
import { ShoppingPilot } from './ShoppingPilot'

vi.mock('@/components/providers/HouseholdIdentityProvider', () => ({
  useHouseholdIdentity: () => ({
    member_id: 'test-child',
    access: 'capture_only',
    display_name: 'Test child',
  }),
}))
afterEach(() => vi.unstubAllGlobals())

describe('shopping capture boundaries', () => {
  it('lets a child compare without loading purchase evidence or adult controls', async () => {
    const calls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        calls.push(url)
        return {
          ok: true,
          json: async () =>
            url.endsWith('/products')
              ? [
                  {
                    id: 'p-1',
                    name: 'Olive oil 68 fl oz',
                    stores: ['Test store'],
                  },
                ]
              : {
                  explanation:
                    'No confirmed current offer. Save a shelf tag for review.',
                  entered_unit_price: 0.4,
                  unit: 'fl oz',
                  alternative_store: null,
                  alternative_package: null,
                  alternative_price: null,
                  alternative_date: null,
                  equivalent_difference: null,
                  conditions: null,
                },
        }
      }),
    )
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <ShoppingPilot />
      </QueryClientProvider>,
    )
    const disclosure = screen
      .getByText('Should I buy this? · Staple price check')
      .closest('details')
    expect(disclosure).not.toBeNull()
    if (!disclosure) throw new Error('Missing shopping disclosure')
    disclosure.open = true
    fireEvent(disclosure, new Event('toggle'))
    await screen.findByRole('option', { name: 'Olive oil 68 fl oz' })
    fireEvent.change(screen.getByLabelText('Item'), {
      target: { value: 'p-1' },
    })
    fireEvent.change(screen.getByLabelText(/Contents of the package/), {
      target: { value: '68 fl oz' },
    })
    fireEvent.change(screen.getByLabelText(/Price for that entire package/), {
      target: { value: '27.2' },
    })
    fireEvent.click(
      screen.getByRole('button', { name: 'Compare recorded offers' }),
    )
    await screen.findByText(
      'No confirmed current offer. Save a shelf tag for review.',
    )
    await waitFor(() =>
      expect(calls).toEqual([
        '/api/captures/shopping/products',
        '/api/captures/shopping/compare',
      ]),
    )
    expect(
      screen.queryByText('Review package, shelf tag or substitute'),
    ).not.toBeInTheDocument()
  })
  it('rejects malformed prices rather than displaying a false comparison', () => {
    expect(() =>
      parseComparison({ explanation: 'test', entered_unit_price: '0.32' }),
    ).toThrow()
    expect(() =>
      parseComparison({
        explanation: 'test',
        entered_unit_price: Number.POSITIVE_INFINITY,
      }),
    ).toThrow()
    expect(() =>
      parseReview([
        {
          id: 'p-1',
          name: 'Oil',
          stores: [],
          offers: [],
          baseline: { line_total: '29.67' },
        },
      ]),
    ).toThrow()
  })
})
