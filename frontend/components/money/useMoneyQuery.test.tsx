import { act, renderHook } from '@testing-library/react'
import { beforeEach, expect, it } from 'vitest'
import { reviewLedgerHref, setMoneyQuery, useMoneyQuery } from './useMoneyQuery'

beforeEach(() =>
  window.history.replaceState({}, '', '/money?tab=spending&month=2026-08'),
)

it('keeps the named month and unrelated filters when changing ledger filters', () => {
  const { result } = renderHook(() => useMoneyQuery('ledgerCategory', 'all'))
  act(() => result.current[1]('Groceries & household'))
  const url = new URL(window.location.href)
  expect(url.searchParams.get('month')).toBe('2026-08')
  expect(url.searchParams.get('ledgerCategory')).toBe('Groceries & household')
  expect(result.current[0]).toBe('Groceries & household')
  act(() => setMoneyQuery({ ledgerSource: 'snaptrade', ledgerPage: '3' }))
  act(() => result.current[1]('Travel'))
  expect(new URLSearchParams(location.search).get('ledgerSource')).toBe(
    'snaptrade',
  )
  expect(new URLSearchParams(location.search).has('ledgerPage')).toBe(false)
})

it('restores controls from a browser history event', () => {
  const { result } = renderHook(() => useMoneyQuery('month', ''))
  act(() => result.current[1]('2026-07'))
  act(() => {
    window.history.replaceState({}, '', '/money?tab=spending&month=2026-08')
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
  expect(result.current[0]).toBe('2026-08')
})

it('links to included category contributions without losing the month', () => {
  const url = new URL(
    reviewLedgerHref('2026-08', 'Peer Payments'),
    'http://localhost',
  )
  expect(Object.fromEntries(url.searchParams)).toMatchObject({
    tab: 'ledger',
    month: '2026-08',
    ledgerInclusion: 'included',
    ledgerStatus: 'all',
    ledgerCategory: 'Peer Payments',
  })
})
