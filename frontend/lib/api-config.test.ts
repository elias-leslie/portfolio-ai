import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { buildApiUrl, getApiBaseUrl, getWsUrl, isDevelopment } from './api-config'

describe('api-config', () => {
  const originalWindow = global.window

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    if (originalWindow === undefined) {
      // @ts-expect-error jsdom test shim
      delete global.window
      return
    }
    global.window = originalWindow
  })

  it('uses localhost backend defaults on the server', () => {
    // @ts-expect-error jsdom test shim
    delete global.window

    expect(getApiBaseUrl()).toBe('http://localhost:8000')
    expect(getWsUrl('/ws/health')).toBe('ws://localhost:8000/ws/health')
    expect(isDevelopment()).toBe(true)
  })

  it('uses same-origin routing on the production domain', () => {
    Object.defineProperty(global, 'window', {
      configurable: true,
      value: {
        location: {
          hostname: 'port.summitflow.dev',
          host: 'port.summitflow.dev',
          protocol: 'https:',
        },
      },
    })

    expect(getApiBaseUrl()).toBe('')
    expect(buildApiUrl('/api/portfolio')).toBe('/api/portfolio')
    expect(getWsUrl('/ws/health')).toBe('wss://port.summitflow.dev/ws/health')
    expect(isDevelopment()).toBe(false)
  })
})
