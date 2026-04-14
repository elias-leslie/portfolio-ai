import { afterEach, describe, expect, it, vi } from 'vitest'
import { proxyRequest, proxyResponse } from './upstream-proxy'

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
})
