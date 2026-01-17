import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { StrategyListItem } from '@/lib/api/strategies'
import { StrategiesTable } from '../StrategiesTable'

const mockStrategies: StrategyListItem[] = [
  {
    id: 'strategy-1',
    symbol: 'AAPL',
    name: 'Apple Momentum Strategy',
    strategyType: 'momentum',
    status: 'active',
    version: 1,
    expectedSharpe: 1.5,
    liveSharpeRatio: 1.2,
    liveWinRate: 0.65,
    tradesCount: 25,
    createdAt: new Date().toISOString(),
    activationDate: new Date().toISOString(),
  },
  {
    id: 'strategy-2',
    symbol: 'GOOGL',
    name: 'Google Value Play',
    strategyType: 'value',
    status: 'testing',
    version: 1,
    expectedSharpe: 1.8,
    liveSharpeRatio: null,
    liveWinRate: null,
    tradesCount: 0,
    createdAt: new Date().toISOString(),
    activationDate: null,
  },
]

describe('StrategiesTable', () => {
  it('renders loading state', () => {
    render(
      <StrategiesTable
        strategies={[]}
        isLoading={true}
        onSelectStrategy={() => {}}
      />,
    )

    // Should show skeletons
    expect(
      document.querySelectorAll('[class*="animate-pulse"]').length,
    ).toBeGreaterThan(0)
  })

  it('renders empty state when no strategies', () => {
    render(
      <StrategiesTable
        strategies={[]}
        isLoading={false}
        onSelectStrategy={() => {}}
      />,
    )

    expect(screen.getByText('No strategies found.')).toBeInTheDocument()
    expect(
      screen.getByText(/Click "Generate Strategies" to create new strategies/),
    ).toBeInTheDocument()
  })

  it('renders table headers', () => {
    render(
      <StrategiesTable
        strategies={mockStrategies}
        isLoading={false}
        onSelectStrategy={() => {}}
      />,
    )

    expect(screen.getByText('Symbol')).toBeInTheDocument()
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Type')).toBeInTheDocument()
    expect(screen.getByText('Status')).toBeInTheDocument()
    expect(screen.getByText('Expected Sharpe')).toBeInTheDocument()
    expect(screen.getByText('Live Sharpe')).toBeInTheDocument()
    expect(screen.getByText('Win Rate')).toBeInTheDocument()
    expect(screen.getByText('Trades')).toBeInTheDocument()
    expect(screen.getByText('Created')).toBeInTheDocument()
  })

  it('renders strategy data correctly', () => {
    render(
      <StrategiesTable
        strategies={mockStrategies}
        isLoading={false}
        onSelectStrategy={() => {}}
      />,
    )

    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('Apple Momentum Strategy')).toBeInTheDocument()
    expect(screen.getByText('momentum')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()

    expect(screen.getByText('GOOGL')).toBeInTheDocument()
    expect(screen.getByText('Google Value Play')).toBeInTheDocument()
    expect(screen.getByText('value')).toBeInTheDocument()
    expect(screen.getByText('testing')).toBeInTheDocument()
  })

  it('calls onSelectStrategy when row is clicked', () => {
    const mockOnSelect = vi.fn()

    render(
      <StrategiesTable
        strategies={mockStrategies}
        isLoading={false}
        onSelectStrategy={mockOnSelect}
      />,
    )

    // Click on the AAPL row
    fireEvent.click(screen.getByText('AAPL'))

    expect(mockOnSelect).toHaveBeenCalledWith('strategy-1')
  })

  it('renders status badges with correct styling', () => {
    render(
      <StrategiesTable
        strategies={mockStrategies}
        isLoading={false}
        onSelectStrategy={() => {}}
      />,
    )

    const activeBadge = screen.getByText('active')
    const testingBadge = screen.getByText('testing')

    expect(activeBadge).toBeInTheDocument()
    expect(testingBadge).toBeInTheDocument()
  })

  it('renders strategy type badges', () => {
    render(
      <StrategiesTable
        strategies={mockStrategies}
        isLoading={false}
        onSelectStrategy={() => {}}
      />,
    )

    expect(screen.getByText('momentum')).toBeInTheDocument()
    expect(screen.getByText('value')).toBeInTheDocument()
  })
})
