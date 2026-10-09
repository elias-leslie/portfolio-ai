import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildForwardedHeaders,
  buildUpstreamUrl,
  MAX_PROXY_BODY_BYTES,
  proxyRequest,
  proxyResponse,
} from './upstream-proxy'

describe('upstream proxy', () => {
  const originalFetch = global.fetch

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('forwards multipart uploads as raw bytes instead of coercing them to text', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ) as unknown as typeof fetch

    const form = new FormData()
    form.append(
      'file',
      new File([Uint8Array.from([0, 1, 2, 3, 255])], 'stmt.pdf', {
        type: 'application/pdf',
      }),
    )
    form.append('account_label', 'Chase Amazon card')

    const request = new Request('http://localhost:3000/api/intake/evidence', {
      method: 'POST',
      body: form,
    })

    await proxyRequest(
      request,
      { params: Promise.resolve({ path: ['intake', 'evidence'] }) },
      'api',
      'POST',
    )

    expect(global.fetch).toHaveBeenCalledTimes(1)
    const [, init] = vi.mocked(global.fetch).mock.calls[0]
    expect(init?.body).toBeInstanceOf(ArrayBuffer)
    expect(init?.cache).toBe('no-store')
    const body = new Uint8Array(init?.body as ArrayBuffer)
    expect(body.byteLength).toBeGreaterThan(32)
    const decoded = new TextDecoder().decode(body)
    expect(decoded).toContain(
      'Content-Disposition: form-data; name="file"; filename=',
    )
    expect(decoded).toContain('Content-Type: application/pdf')
    expect(decoded).toContain('Chase Amazon card')
  })

  it('marks proxied responses as uncached', async () => {
    const proxied = proxyResponse(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Content-Disposition': 'attachment; filename="data.json"',
        },
      }),
    )

    expect(proxied.headers.get('Cache-Control')).toBe('no-store, max-age=0')
    expect(proxied.headers.get('Pragma')).toBe('no-cache')
    expect(proxied.headers.get('Expires')).toBe('0')
    expect(proxied.headers.get('Content-Disposition')).toBe(
      'attachment; filename="data.json"',
    )
  })

  describe('request guard', () => {
    const okFetch = () => {
      global.fetch = vi
        .fn()
        .mockResolvedValue(
          new Response('{}', { status: 200 }),
        ) as unknown as typeof fetch
    }
    const send = (url: string, init: RequestInit, path = ['plaid', 'sync']) =>
      proxyRequest(
        new Request(url, init),
        { params: Promise.resolve({ path }) },
        'api',
        (init.method ?? 'GET').toUpperCase(),
      )

    afterEach(() => {
      vi.unstubAllEnvs()
    })

    it('proxies same-origin local POSTs and CLI requests without Origin', async () => {
      okFetch()
      const sameOrigin = await send('http://localhost:3000/api/plaid/sync', {
        method: 'POST',
        headers: {
          origin: 'http://localhost:3000',
          'sec-fetch-site': 'same-origin',
        },
        body: '{}',
      })
      const cli = await send('http://127.0.0.1:3000/api/plaid/sync', {
        method: 'POST',
        body: '{}',
      })
      expect(sameOrigin.status).toBe(200)
      expect(cli.status).toBe(200)
      expect(global.fetch).toHaveBeenCalledTimes(2)
    })

    it('rejects cross-site and mismatched-origin state changes', async () => {
      okFetch()
      const attempts: Record<string, string>[] = [
        { 'sec-fetch-site': 'cross-site' },
        { origin: 'https://attacker.example' },
        { origin: 'http://localhost:3001' },
        { origin: 'null' },
      ]
      for (const headers of attempts) {
        const response = await send('http://localhost:3000/api/plaid/sync', {
          method: 'POST',
          headers,
          body: '{}',
        })
        expect(response.status).toBe(403)
      }
      expect(global.fetch).not.toHaveBeenCalled()
    })

    it('rejects DNS-rebound hosts without an Access assertion', async () => {
      okFetch()
      const rebound = await send(
        'http://rebind.attacker.example:3000/api/plaid/sync',
        {
          method: 'POST',
          headers: { origin: 'http://rebind.attacker.example:3000' },
          body: '{}',
        },
      )
      const read = await send(
        'http://rebind.attacker.example:3000/api/identity',
        {},
        ['identity'],
      )
      expect(rebound.status).toBe(403)
      expect(read.status).toBe(403)
      expect(global.fetch).not.toHaveBeenCalled()
    })

    it('keeps Access-authenticated public host requests working', async () => {
      okFetch()
      const response = await send(
        'https://port.summitflow.dev/api/plaid/sync',
        {
          method: 'POST',
          headers: {
            origin: 'https://port.summitflow.dev',
            'sec-fetch-site': 'same-origin',
            'cf-access-jwt-assertion': 'signed.jwt.value',
          },
          body: '{}',
        },
      )
      expect(response.status).toBe(200)
      const [, init] = vi.mocked(global.fetch).mock.calls[0]
      expect(new Headers(init?.headers).get('cf-access-jwt-assertion')).toBe(
        'signed.jwt.value',
      )
    })

    it('limits public hosts to FRONTEND_PUBLIC_HOSTS when configured', async () => {
      okFetch()
      vi.stubEnv('FRONTEND_PUBLIC_HOSTS', 'port.summitflow.dev')
      const response = await send('https://other.example/api/identity', {
        headers: { 'cf-access-jwt-assertion': 'signed.jwt.value' },
      })
      expect(response.status).toBe(421)
      expect(global.fetch).not.toHaveBeenCalled()
    })

    it('rejects declared and streamed bodies over the upload bound', async () => {
      okFetch()
      const declared = await send('http://localhost:3000/api/intake/evidence', {
        method: 'POST',
        headers: { 'content-length': String(MAX_PROXY_BODY_BYTES + 1) },
        body: 'x',
      })
      expect(declared.status).toBe(413)

      const chunk = new Uint8Array(1024 * 1024)
      let sent = 0
      const stream = new ReadableStream<Uint8Array>({
        pull(controller) {
          if (sent > MAX_PROXY_BODY_BYTES) return controller.close()
          sent += chunk.byteLength
          controller.enqueue(chunk)
        },
      })
      const streamed = await send('http://localhost:3000/api/intake/evidence', {
        method: 'POST',
        body: stream,
        duplex: 'half',
      } as RequestInit)
      expect(streamed.status).toBe(413)
      expect(global.fetch).not.toHaveBeenCalled()
    })
  })

  it('rejects traversal and encoded-slash path segments', () => {
    for (const path of [
      ['..', 'admin'],
      ['.'],
      ['a%2F..'],
      ['a%2fb'],
      ['a\\b'],
      ['%2e%2e'],
      [''],
    ]) {
      expect(() => buildUpstreamUrl('api', path)).toThrow()
    }
    expect(buildUpstreamUrl('api', ['market', 'BRK.B'], 'q=1')).toMatch(
      /\/api\/market\/BRK\.B\?q=1$/,
    )
    expect(buildUpstreamUrl('api', ['merchants', 'Joe Diner'])).toMatch(
      /\/api\/merchants\/Joe%20Diner$/,
    )
  })

  it('forwards only allowlisted headers', () => {
    const headers = buildForwardedHeaders(
      new Request('http://localhost:3000/api/x', {
        headers: {
          accept: 'application/json',
          cookie: 'CF_Authorization=abc',
          'cf-access-jwt-assertion': 'jwt',
          'x-forwarded-for': '198.51.100.7',
          'x-agent-hub-internal': 'should-not-pass',
          'x-custom-anything': 'nope',
          connection: 'keep-alive',
        },
      }),
    )
    expect(headers.get('accept')).toBe('application/json')
    expect(headers.get('cookie')).toBe('CF_Authorization=abc')
    expect(headers.get('cf-access-jwt-assertion')).toBe('jwt')
    expect(headers.get('x-forwarded-for')).toBe('198.51.100.7')
    expect(headers.get('x-agent-hub-internal')).toBeNull()
    expect(headers.get('x-custom-anything')).toBeNull()
    expect(headers.get('connection')).toBeNull()
    expect(headers.get('host')).toBeNull()
  })
})
