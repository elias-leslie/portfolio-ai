'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SnapTradePanel } from '../SnapTradePanel'

const useSnapTradeStatusMock = vi.fn()
const configureSnapTradeMutateAsync = vi.fn()
const createPortalMutateAsync = vi.fn()
const syncSnapTradeMutateAsync = vi.fn()

vi.mock('@/lib/hooks/useSnapTrade', () => ({
  useSnapTradeStatus: () => useSnapTradeStatusMock(),
  useConfigureSnapTrade: () => ({
    mutateAsync: configureSnapTradeMutateAsync,
    isPending: false,
  }),
  useCreateSnapTradeConnectionPortal: () => ({
    mutateAsync: createPortalMutateAsync,
    isPending: false,
  }),
  useSyncSnapTrade: () => ({
    mutateAsync: syncSnapTradeMutateAsync,
    isPending: false,
  }),
}))

const configuredStatus = {
  configured: true,
  clientIdConfigured: true,
  consumerKeyConfigured: true,
  configurationUpdatedAt: '2026-05-17T14:00:00Z',
  encryptionReady: true,
  accessMode: 'read_only' as const,
  defaultBroker: 'FIDELITY',
  redirectUri: 'https://port.summitflow.dev/money',
  userRegistered: false,
  connectionCount: 0,
  accountCount: 0,
  positionCount: 0,
  activityCount: 0,
  lastSuccessfulSyncAt: null,
  lastError: null,
  connections: [],
  accounts: [],
}

describe('SnapTradePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useSnapTradeStatusMock.mockReturnValue({
      data: configuredStatus,
      isLoading: false,
    })
    configureSnapTradeMutateAsync.mockResolvedValue(configuredStatus)
    createPortalMutateAsync.mockResolvedValue({
      portalUrl: 'https://snaptrade.example/connect',
    })
    syncSnapTradeMutateAsync.mockResolvedValue({})
  })

  it('shows saved SnapTrade credentials separately from pending brokerage connection', () => {
    render(<SnapTradePanel />)

    expect(
      screen.getByText('Credentials configured; brokerage connection pending'),
    ).toBeInTheDocument()
    expect(screen.getByText('Client ID saved')).toBeInTheDocument()
    expect(screen.getByText('Consumer key saved')).toBeInTheDocument()
    expect(screen.getByText('Portal connection pending')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /connect brokerage/i }),
    ).toBeEnabled()
  })

  it('keeps existing secret fields when saving non-secret SnapTrade settings', async () => {
    const user = userEvent.setup()
    render(<SnapTradePanel />)

    await user.click(screen.getByRole('button', { name: 'Configure' }))

    expect(await screen.findByDisplayValue('FIDELITY')).toBeInTheDocument()
    expect(
      screen.getByDisplayValue('https://port.summitflow.dev/money'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Client ID')).not.toBeRequired()
    expect(screen.getByLabelText('Consumer key')).not.toBeRequired()

    await user.click(screen.getByRole('button', { name: 'Save configuration' }))

    expect(configureSnapTradeMutateAsync).toHaveBeenCalledWith({
      redirectUri: 'https://port.summitflow.dev/money',
      defaultBroker: 'FIDELITY',
    })
  })
})
