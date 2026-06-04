'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SnapTradePanel } from '../SnapTradePanel'

const useSnapTradeStatusMock = vi.fn()
const configureSnapTradeMutateAsync = vi.fn()
const createPortalMutateAsync = vi.fn()
const syncSnapTradeMutateAsync = vi.fn()
const useSnapTradeOrdersMock = vi.fn()

vi.mock('@/lib/hooks/useSnapTrade', () => ({
  useSnapTradeStatus: () => useSnapTradeStatusMock(),
  useSnapTradeOrders: (args: unknown) => useSnapTradeOrdersMock(args),
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
  sourceAccountCount: 0,
  positionCount: 0,
  activityCount: 0,
  orderCount: 0,
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
    useSnapTradeOrdersMock.mockReturnValue({
      data: { orders: [] },
      isLoading: false,
      error: null,
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

  it('renders synced trade history in the SnapTrade account surface', () => {
    useSnapTradeStatusMock.mockReturnValue({
      data: {
        ...configuredStatus,
        userRegistered: true,
        connectionCount: 1,
        accountCount: 1,
        sourceAccountCount: 1,
        positionCount: 1,
        activityCount: 3,
        orderCount: 2,
        accounts: [
          {
            accountId: 'acct-roth',
            name: 'ROTH IRA',
            institutionName: 'Fidelity',
            accountMask: '1234',
            portfolioAccountType: 'Roth',
            balance: 49541.96,
            marketValue: 49541.96,
            valuationSource: 'broker',
            quoteAsOf: null,
            cashBalance: 49541.96,
            currency: 'USD',
            lastSyncedAt: '2026-06-03T22:30:00Z',
          },
        ],
      },
      isLoading: false,
    })
    useSnapTradeOrdersMock.mockReturnValue({
      data: {
        orders: [
          {
            accountId: 'acct-roth',
            accountName: 'ROTH IRA',
            institutionName: 'Fidelity',
            accountMask: '1234',
            brokerageOrderId: 'order-1',
            status: 'EXECUTED',
            action: 'BUY',
            symbol: 'VGT',
            rawSymbol: 'VGT',
            filledQuantity: 395,
            executionPrice: 125.09,
            orderType: 'Market',
            timeInForce: 'Day',
            timePlaced: '2026-06-02T04:00:00Z',
            timeUpdated: '2026-06-02T04:00:00Z',
            timeExecuted: '2026-06-02T04:00:00Z',
            currency: 'USD',
            lastSyncedAt: '2026-06-03T22:30:00Z',
          },
        ],
      },
      isLoading: false,
      error: null,
    })

    render(<SnapTradePanel />)

    expect(screen.getByText('Trade history')).toBeInTheDocument()
    expect(screen.getByText('1 recent order')).toBeInTheDocument()
    expect(screen.getByText('VGT')).toBeInTheDocument()
    expect(screen.getByText('EXECUTED')).toBeInTheDocument()
    expect(screen.getByText('BUY · Market')).toBeInTheDocument()
    expect(screen.getByText('395 @ $125.09')).toBeInTheDocument()
    expect(screen.getByText('$49,410.55')).toBeInTheDocument()
  })
})
