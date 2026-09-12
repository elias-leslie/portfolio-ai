import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { HouseholdShell } from './HouseholdShell'

const state = vi.hoisted(() => ({ pathname: '/money', replace: vi.fn() }))
vi.mock('next/navigation', () => ({
  usePathname: () => state.pathname,
  useRouter: () => ({ replace: state.replace }),
}))
vi.mock('@/components/providers/HouseholdIdentityProvider', () => ({
  useHouseholdIdentity: () => ({
    member_id: 'test-child',
    display_name: 'Test child',
    access: 'capture_only',
  }),
}))
vi.mock('@/components/Navigation', () => ({
  Navigation: () => <div>Financial navigation</div>,
}))
vi.mock('@/components/chat/JennyChatWidget', () => ({
  JennyChatWidget: () => <div>Financial chat</div>,
}))

beforeEach(() => {
  state.pathname = '/money'
  state.replace.mockClear()
})

it('redirects a child before financial components mount or fetch data', () => {
  const finance = vi.fn(() => <div>Private money</div>)
  const FinancialPage = finance
  render(
    <QueryClientProvider client={new QueryClient()}>
      <HouseholdShell>
        <FinancialPage />
      </HouseholdShell>
    </QueryClientProvider>,
  )
  expect(state.replace).toHaveBeenCalledWith('/capture')
  expect(finance).not.toHaveBeenCalled()
  expect(screen.queryByText('Financial navigation')).not.toBeInTheDocument()
  expect(screen.queryByText('Financial chat')).not.toBeInTheDocument()
})

it('shows the capture page within the child shell', () => {
  state.pathname = '/capture'
  render(
    <QueryClientProvider client={new QueryClient()}>
      <HouseholdShell>
        <h1>Capture test page</h1>
      </HouseholdShell>
    </QueryClientProvider>,
  )
  expect(
    screen.getByRole('heading', { name: 'Capture test page' }),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  expect(state.replace).not.toHaveBeenCalled()
})
