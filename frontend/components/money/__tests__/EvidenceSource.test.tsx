import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { apiRequest } from '@/lib/api/client'
import { EvidenceSource, parseEvidenceSource } from '../EvidenceSource'
import { ImportCenterSidebar } from '../ImportCenterSidebar'

vi.mock('@/lib/api/client', () => ({ apiRequest: vi.fn() }))
vi.mock('../DocumentCard', () => ({
  DocumentCard: ({ document }: { document: { filename: string } }) => (
    <p>{document.filename}</p>
  ),
}))
const request = vi.mocked(apiRequest)
const emptySource = {
  reviewId: 'exact-review',
  text: 'Original line',
  questions: ['Which account paid this?'],
  truncated: false,
  arithmetic: [],
}
function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {children}
    </QueryClientProvider>
  )
}
beforeEach(() => {
  request.mockReset()
  window.history.replaceState({}, '', '/money?tab=intake')
})
it('loads source only on request and binds searches to the displayed review', async () => {
  request.mockResolvedValue(emptySource)
  render(
    <EvidenceSource
      documentId="receipt"
      reviewId="exact-review"
      fileAvailable
    />,
    { wrapper },
  )
  expect(request).not.toHaveBeenCalled()
  const disclosure = screen
    .getByText('Source evidence & receipt arithmetic')
    .closest('details')!
  // jsdom has no native toggle default action.
  disclosure.open = true
  fireEvent(disclosure, new Event('toggle'))
  await screen.findByText('Original line')
  expect(request.mock.calls[0][0]).toContain('review_id=exact-review')
  expect(
    screen.getByRole('link', { name: 'Open original file' }),
  ).toHaveAttribute('href', '/api/intake/evidence/receipt/file')
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Find in source'), 'tax')
  await user.click(screen.getByRole('button', { name: 'Find' }))
  await waitFor(() =>
    expect(request.mock.calls.at(-1)?.[0]).toContain(
      'search=tax&review_id=exact-review',
    ),
  )
})
it('does not render mismatched review text or malformed money as evidence', async () => {
  expect(() =>
    parseEvidenceSource({
      ...emptySource,
      arithmetic: [{ merchant: 'Store', readableLines: 1, lineTotal: '12.00' }],
    }),
  ).toThrow()
  request.mockResolvedValue({
    ...emptySource,
    reviewId: 'newer',
    text: 'Wrong source',
  })
  render(
    <EvidenceSource
      documentId="receipt"
      reviewId="exact-review"
      fileAvailable={false}
    />,
    { wrapper },
  )
  const disclosure = screen
    .getByText('Source evidence & receipt arithmetic')
    .closest('details')!
  disclosure.open = true
  fireEvent(disclosure, new Event('toggle'))
  await screen.findByRole('alert')
  expect(screen.queryByText('Wrong source')).not.toBeInTheDocument()
})
it('uses the full pending count and loads older pages without turning an error into all-clear', async () => {
  request
    .mockResolvedValueOnce({
      items: [{ id: 'one', filename: 'First pending receipt' }],
      pendingCount: 2,
      totalCount: 2,
      offset: 0,
      limit: 1,
    })
    .mockResolvedValueOnce({
      items: [{ id: 'older', filename: 'Older pending receipt' }],
      pendingCount: 2,
      totalCount: 2,
      offset: 1,
      limit: 1,
    })
  render(<ImportCenterSidebar />, { wrapper })
  expect(
    screen.queryByText('No pending document decisions.'),
  ).not.toBeInTheDocument()
  await screen.findByRole('button', { name: 'Pending decisions (2)' })
  await userEvent.click(
    screen.getByRole('button', { name: 'Show more evidence' }),
  )
  await screen.findByText('Older pending receipt')
  expect(request.mock.calls[1][0]).toContain('view=pending&limit=8&offset=1')
})
