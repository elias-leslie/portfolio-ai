import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatRelativeTime } from './utils'

describe('formatRelativeTime', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns a forward-looking label for near-future timestamps', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-12T13:00:00.000Z'))

    expect(formatRelativeTime('2026-03-12T13:05:00.000Z')).toBe('In 5m')
    expect(formatRelativeTime('2026-03-12T15:00:00.000Z')).toBe('In 2h')
  })

  it('returns Unknown for invalid timestamps', () => {
    expect(formatRelativeTime('not-a-date')).toBe('Unknown')
  })
})
