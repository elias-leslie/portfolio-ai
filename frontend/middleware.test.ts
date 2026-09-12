import { NextRequest } from 'next/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { middleware } from './middleware'

afterEach(() => vi.unstubAllGlobals())

describe('Cloudflare Access boundary', () => {
  it('allows loopback development without an Access token', async () => {
    const response = await middleware(
      new NextRequest('http://127.0.0.1:3000/money'),
    )

    expect(response.status).toBe(200)
    expect(response.headers.get('x-middleware-next')).toBe('1')
  })

  it('denies a public hostname without an Access assertion', async () => {
    const response = await middleware(
      new NextRequest('https://port.summitflow.dev/'),
    )

    expect(response.status).toBe(403)
    expect(await response.text()).toContain('Cloudflare Access')
  })

  it('denies a forged JWT-shaped Access assertion', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response('Unverified assertion', { status: 403 }),
        ),
    )
    const response = await middleware(
      new NextRequest('https://port.summitflow.dev/', {
        headers: { 'Cf-Access-Jwt-Assertion': 'header.payload.signature' },
      }),
    )

    expect(response.status).toBe(403)
  })

  it('fails closed when backend identity verification is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const response = await middleware(
      new NextRequest('https://port.summitflow.dev/', {
        headers: { 'Cf-Access-Jwt-Assertion': 'header.payload.signature' },
      }),
    )
    expect(response.status).toBe(503)
    expect(response.headers.get('x-middleware-next')).toBeNull()
  })
})
