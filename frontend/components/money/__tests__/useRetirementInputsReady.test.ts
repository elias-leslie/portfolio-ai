import { act, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useRetirementInputsReady } from '../useRetirementInputsReady'

afterEach(() => vi.useRealTimers())

it('waits for source defaults and starts only the settled request', () => {
  vi.useFakeTimers()
  const { result, rerender } = renderHook(
    ({ key, waiting }) => useRetirementInputsReady(key, waiting),
    { initialProps: { key: 'initial', waiting: true } },
  )
  act(() => vi.advanceTimersByTime(1000))
  expect(result.current).toBe(false)
  rerender({ key: 'initial', waiting: false })
  act(() => vi.advanceTimersByTime(250))
  rerender({ key: 'income-seeded', waiting: false })
  act(() => vi.advanceTimersByTime(250))
  rerender({ key: 'child-cost-seeded', waiting: false })
  act(() => vi.advanceTimersByTime(299))
  expect(result.current).toBe(false)
  act(() => vi.advanceTimersByTime(1))
  expect(result.current).toBe(true)
  rerender({ key: 'explicit-run', waiting: false })
  expect(result.current).toBe(false)
  act(() => vi.advanceTimersByTime(300))
  expect(result.current).toBe(true)
})

it('clears readiness when required sources reload, even for an unchanged request', () => {
  vi.useFakeTimers()
  const { result, rerender } = renderHook(
    ({ waiting }) => useRetirementInputsReady('same', waiting),
    { initialProps: { waiting: false } },
  )
  act(() => vi.advanceTimersByTime(300))
  expect(result.current).toBe(true)
  rerender({ waiting: true })
  expect(result.current).toBe(false)
  rerender({ waiting: false })
  expect(result.current).toBe(false)
  act(() => vi.advanceTimersByTime(300))
  expect(result.current).toBe(true)
})
