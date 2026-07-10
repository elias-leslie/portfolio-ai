import { NextRequest } from 'next/server'
import { describe, expect, it } from 'vitest'
import { middleware } from './middleware'

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
    const response = await middleware(
      new NextRequest('https://port.summitflow.dev/', {
        headers: { 'Cf-Access-Jwt-Assertion': 'header.payload.signature' },
      }),
    )

    expect(response.status).toBe(403)
  })
})
