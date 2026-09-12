import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { get } from '@/lib/api/client'
import { SymbolLotEvidence } from '../SymbolLotEvidence'

vi.mock('@/lib/api/client', () => ({ get: vi.fn() }))

it('loads only when opened and keeps missing lots distinct from zero gains', async () => {
  vi.mocked(get).mockResolvedValue({
    quotePrice: 150,
    quoteSource: 'broker',
    quoteTime: null,
    accounts: [
      {
        accountId: 'real',
        accountName: 'Brokerage',
        taxable: true,
        positionShares: 10,
        recordedLotShares: 0,
        coverage: 'missing',
        lots: [],
      },
    ],
  })
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <SymbolLotEvidence symbol="AAPL" />
    </QueryClientProvider>,
  )
  expect(get).not.toHaveBeenCalled()
  await userEvent.click(
    screen.getByRole('button', { name: 'Review tax lots before a sale' }),
  )
  expect(await screen.findByText('Brokerage')).toBeInTheDocument()
  expect(
    screen.getByText(
      /Complete acquisition dates and basis are not established/,
    ),
  ).toBeInTheDocument()
  expect(screen.queryByText(/Gain at quote/)).not.toBeInTheDocument()
  expect(get).toHaveBeenCalledWith('/api/portfolio/tlh/lots/AAPL')
})
