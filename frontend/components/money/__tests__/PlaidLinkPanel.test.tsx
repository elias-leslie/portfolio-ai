'use client'

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PlaidLinkPanel } from '../PlaidLinkPanel'

const usePlaidStatusMock = vi.fn()
const configurePlaidMutateAsync = vi.fn()
const createLinkTokenMutateAsync = vi.fn()
const exchangePublicTokenMutateAsync = vi.fn()
const syncPlaidMutateAsync = vi.fn()
const removeItemMutateAsync = vi.fn()
const openPlaidMock = vi.fn()

vi.mock('react-plaid-link', () => ({
  usePlaidLink: () => ({
    open: openPlaidMock,
    ready: true,
  }),
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
    usePlaidStatusMock.mockReturnValue({
      data: configuredStatus,
      isLoading: false,
    })
    configurePlaidMutateAsync.mockResolvedValue(configuredStatus)
    createLinkTokenMutateAsync.mockResolvedValue({ linkToken: 'link-token' })
    exchangePublicTokenMutateAsync.mockResolvedValue({})
    syncPlaidMutateAsync.mockResolvedValue({})
    removeItemMutateAsync.mockResolvedValue({})
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
})
