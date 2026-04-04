import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getApiBaseUrl, getWsUrl } from './api-config'

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
    expect(getWsUrl('/ws/health')).toBe('wss://port.summitflow.dev/ws/health')
  })

  it('keeps api and websocket traffic same-origin on localhost too', () => {
    Object.defineProperty(global, 'window', {
      configurable: true,
      value: {
        location: {
          hostname: 'localhost',
          host: 'localhost:3200',
          protocol: 'http:',
        },
      },
    })

    expect(getApiBaseUrl()).toBe('')
    expect(getWsUrl('/ws/health')).toBe('ws://localhost:3200/ws/health')
  })

  it('keeps api and websocket traffic same-origin on non-local browser hosts', () => {
    Object.defineProperty(global, 'window', {
      configurable: true,
      value: {
        location: {
          hostname: '192.168.1.100',
          host: '192.168.1.100:3000',
          protocol: 'http:',
        },
      },
    })

    expect(getApiBaseUrl()).toBe('')
    expect(getWsUrl('/ws/health')).toBe('ws://192.168.1.100:3000/ws/health')
  })
})
