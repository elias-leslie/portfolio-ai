'use client'

import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { usePlaidLink } from 'react-plaid-link'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PlaidLinkPanel } from '../PlaidLinkPanel'

const usePlaidStatusMock = vi.fn()
const configurePlaidMutateAsync = vi.fn()
const createLinkTokenMutateAsync = vi.fn()
const exchangePublicTokenMutateAsync = vi.fn()
const syncPlaidMutateAsync = vi.fn()
const removeItemMutateAsync = vi.fn()
const openPlaidMock = vi.fn()
let plaidOptions: Parameters<typeof usePlaidLink>[0]

vi.mock('react-plaid-link', () => ({
  usePlaidLink: (options: Parameters<typeof usePlaidLink>[0]) => {
    plaidOptions = options
    return {
      open: openPlaidMock,
      ready: true,
    }
  },
}))

vi.mock('@/lib/hooks/usePlaid', () => ({
  usePlaidStatus: () => usePlaidStatusMock(),
  useConfigurePlaid: () => ({
    mutateAsync: configurePlaidMutateAsync,
    isPending: false,
  }),
  useCreatePlaidLinkToken: () => ({
    mutateAsync: createLinkTokenMutateAsync,
    isPending: false,
  }),
  useExchangePlaidPublicToken: () => ({
    mutateAsync: exchangePublicTokenMutateAsync,
    isPending: false,
  }),
  useSyncPlaidItems: () => ({
    mutateAsync: syncPlaidMutateAsync,
    isPending: false,
  }),
  useRemovePlaidItem: () => ({
    mutateAsync: removeItemMutateAsync,
    isPending: false,
  }),
}))

const configuredStatus = {
  configured: true,
  clientIdConfigured: true,
  secretConfigured: true,
  configurationUpdatedAt: '2026-05-17T14:00:00Z',
  encryptionReady: true,
  environment: 'production',
  products: ['transactions'],
  countryCodes: ['US'],
  redirectUri: 'https://portfolio-ai.example/money',
  itemCount: 0,
  accountCount: 0,
  transactionCount: 0,
  lastSuccessfulSyncAt: null,
  items: [],
}

describe('PlaidLinkPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    window.history.replaceState({}, '', '/money')
    usePlaidStatusMock.mockReturnValue({
      data: configuredStatus,
      isLoading: false,
    })
    configurePlaidMutateAsync.mockResolvedValue(configuredStatus)
    createLinkTokenMutateAsync.mockResolvedValue({ linkToken: 'link-token' })
    exchangePublicTokenMutateAsync.mockResolvedValue({ sync: { errors: [] } })
    syncPlaidMutateAsync.mockResolvedValue({ errors: [] })
    removeItemMutateAsync.mockResolvedValue({})
  })

  it('keeps loading and failed reads distinct from an unconfigured connection', async () => {
    const retry = vi.fn()
    usePlaidStatusMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      refetch: retry,
    })
    const view = render(<PlaidLinkPanel />)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Loading Plaid connection status',
    )
    expect(screen.queryByText('Not configured')).not.toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Configure' }),
    ).not.toBeInTheDocument()
    usePlaidStatusMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Offline'),
      refetch: retry,
    })
    view.rerender(<PlaidLinkPanel />)
    expect(screen.getByRole('alert')).toHaveTextContent(
      'connection status is unavailable',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Retry Plaid status' }),
    )
    expect(retry).toHaveBeenCalledOnce()
  })

  it('shows saved Plaid credentials separately from pending institution connection', () => {
    render(<PlaidLinkPanel />)

    expect(
      screen.getByText(
        'Credentials configured; institution connection pending',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Client ID saved')).toBeInTheDocument()
    expect(screen.getByText('Secret saved')).toBeInTheDocument()
    expect(screen.getByText('Production')).toBeInTheDocument()
    expect(screen.getByText('OAuth authorization pending')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /connect bank/i })).toBeEnabled()
    expect(screen.queryByText(/chase/i)).not.toBeInTheDocument()
  })

  it('keeps existing secret fields when saving non-secret Plaid settings', async () => {
    const user = userEvent.setup()
    render(<PlaidLinkPanel />)

    await user.click(screen.getByRole('button', { name: 'Configure' }))

    expect(await screen.findByDisplayValue('transactions')).toBeInTheDocument()
    expect(screen.getByDisplayValue('US')).toBeInTheDocument()
    expect(
      screen.getByDisplayValue('https://portfolio-ai.example/money'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Client ID')).not.toBeRequired()
    expect(screen.getByLabelText('Secret')).not.toBeRequired()

    await user.click(screen.getByRole('button', { name: 'Save configuration' }))

    expect(configurePlaidMutateAsync).toHaveBeenCalledWith({
      environment: 'production',
      products: ['transactions'],
      countryCodes: ['US'],
      redirectUri: 'https://portfolio-ai.example/money',
    })
  })

  it('opens Plaid Link when starting the bank connection', async () => {
    const user = userEvent.setup()
    render(<PlaidLinkPanel />)

    await user.click(screen.getByRole('button', { name: /connect bank/i }))

    expect(createLinkTokenMutateAsync).toHaveBeenCalled()
    await waitFor(() => expect(openPlaidMock).toHaveBeenCalled())
  })

  it('syncs the existing item on update success without exchanging a token', async () => {
    usePlaidStatusMock.mockReturnValue({
      data: {
        ...configuredStatus,
        itemCount: 1,
        items: [
          {
            itemId: 'item-1',
            institutionName: 'Bank',
            status: 'active',
            lastSuccessfulSyncAt: null,
            lastError: null,
          },
        ],
      },
      isLoading: false,
    })
    render(<PlaidLinkPanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Add accounts' }))
    await waitFor(() => expect(openPlaidMock).toHaveBeenCalled())
    await act(async () => {
      await plaidOptions.onSuccess?.(
        'unused-update-token',
        {} as Parameters<NonNullable<typeof plaidOptions.onSuccess>>[1],
      )
    })
    expect(syncPlaidMutateAsync).toHaveBeenCalledWith({ itemId: 'item-1' })
    expect(exchangePublicTokenMutateAsync).not.toHaveBeenCalled()
    expect(
      window.localStorage.getItem('portfolio-ai.plaid.link_token'),
    ).toBeNull()
  })

  it('retains update mode across an OAuth redirect', async () => {
    window.localStorage.setItem('portfolio-ai.plaid.link_token', 'saved-token')
    window.localStorage.setItem(
      'portfolio-ai.plaid.link_context',
      JSON.stringify({ mode: 'update', itemId: 'item-1' }),
    )
    window.history.replaceState({}, '', '/money?oauth_state_id=test')
    render(<PlaidLinkPanel />)
    await waitFor(() => expect(openPlaidMock).toHaveBeenCalled())
    expect(
      'receivedRedirectUri' in plaidOptions && plaidOptions.receivedRedirectUri,
    ).toContain('oauth_state_id=test')
    await act(async () => {
      await plaidOptions.onSuccess?.(
        'unused-update-token',
        {} as Parameters<NonNullable<typeof plaidOptions.onSuccess>>[1],
      )
    })
    expect(syncPlaidMutateAsync).toHaveBeenCalledWith({ itemId: 'item-1' })
    expect(exchangePublicTokenMutateAsync).not.toHaveBeenCalled()
    expect(
      window.localStorage.getItem('portfolio-ai.plaid.link_context'),
    ).toBeNull()
  })

  it('shows a linked item with no successful sync distinctly', () => {
    usePlaidStatusMock.mockReturnValue({
      data: {
        ...configuredStatus,
        itemCount: 1,
        items: [
          {
            itemId: 'item-1',
            institutionName: 'Bank',
            status: 'active',
            lastSuccessfulSyncAt: null,
            lastError: null,
          },
        ],
      },
      isLoading: false,
    })
    render(<PlaidLinkPanel />)
    expect(screen.getByText('Connected; sync pending')).toBeInTheDocument()
    expect(screen.queryByText('Sync enabled')).not.toBeInTheDocument()
  })

  it('retains a visible sync error after a successful account update', async () => {
    window.localStorage.setItem('portfolio-ai.plaid.link_token', 'saved-token')
    window.localStorage.setItem(
      'portfolio-ai.plaid.link_context',
      JSON.stringify({ mode: 'update', itemId: 'item-1' }),
    )
    window.history.replaceState({}, '', '/money?oauth_state_id=test')
    syncPlaidMutateAsync.mockResolvedValue({
      errors: [{ errorMessage: 'Transactions unavailable' }],
    })
    render(<PlaidLinkPanel />)
    await waitFor(() => expect(openPlaidMock).toHaveBeenCalled())
    await act(async () => {
      await plaidOptions.onSuccess?.(
        'unused-update-token',
        {} as Parameters<NonNullable<typeof plaidOptions.onSuccess>>[1],
      )
    })
    expect(
      screen.getByText(/Accounts updated; sync has 1 issue/),
    ).toBeInTheDocument()
  })
})
