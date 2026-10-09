import { getApiBaseUrl } from './api-config'

/**
 * Mirrors the backend's household upload request bound
 * (MAX_HOUSEHOLD_UPLOAD_REQUEST_BYTES: 50 MB of evidence plus 1 MB of
 * multipart overhead) so oversized bodies are refused before buffering.
 */
export const MAX_PROXY_BODY_BYTES = 51 * 1024 * 1024

const ACCESS_ASSERTION_HEADER = 'cf-access-jwt-assertion'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

/**
 * Client headers the backend or its audit/identity checks actually read.
 * Everything else (hop-by-hop headers, internal service secrets, arbitrary
 * x-* headers) is dropped. Forwarding/edge headers stay because the backend
 * uses them only to withhold local authority, never to grant it.
 */
const FORWARDED_HEADER_ALLOWLIST = [
  'accept',
  'accept-language',
  'authorization',
  'cache-control',
  'cf-access-jwt-assertion',
  'cf-connecting-ip',
  'cf-ray',
  'content-type',
  'cookie',
  'idempotency-key',
  'if-match',
  'if-modified-since',
  'if-none-match',
  'origin',
  'range',
  'referer',
  'sec-fetch-dest',
  'sec-fetch-mode',
  'sec-fetch-site',
  'user-agent',
  'x-forwarded-for',
  'x-forwarded-proto',
  'x-request-id',
] as const

export class ProxyRejection extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function rejectionResponse(rejection: ProxyRejection): Response {
  return new Response(JSON.stringify({ detail: rejection.message }), {
    status: rejection.status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store, max-age=0',
    },
  })
}

export function isLocalHostname(hostname: string): boolean {
  const normalized = hostname.toLowerCase().replace(/^\[|\]$/g, '')
  return (
    normalized === 'localhost' ||
    normalized === '127.0.0.1' ||
    normalized === '::1' ||
    normalized.endsWith('.localhost')
  )
}

function requestHost(request: Request): string {
  return (
    request.headers.get('host') ?? new URL(request.url).host
  ).toLowerCase()
}

function hostnameOf(host: string): string {
  if (host.startsWith('[')) return host.slice(1, host.indexOf(']'))
  return host.split(':', 1)[0] ?? ''
}

function configuredPublicHosts(): string[] {
  return (process.env.FRONTEND_PUBLIC_HOSTS ?? '')
    .split(',')
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean)
}

/**
 * Refuse requests a hostile page could aim at the loopback proxy.
 *
 * - DNS rebinding: a non-local Host is only proxied with a Cloudflare Access
 *   assertion (verified by the backend) and, when FRONTEND_PUBLIC_HOSTS is
 *   set, only for those hosts.
 * - CSRF: state-changing methods must not be cross-site and any Origin must
 *   match the Host that received the request.
 */
export function assertProxyRequestAllowed(
  request: Request,
  method: string,
): void {
  const host = requestHost(request)
  const hostname = hostnameOf(host)
  if (!hostname) throw new ProxyRejection(400, 'Missing request host.')
  if (!isLocalHostname(hostname)) {
    const publicHosts = configuredPublicHosts()
    if (publicHosts.length > 0 && !publicHosts.includes(hostname)) {
      throw new ProxyRejection(421, 'This host is not served here.')
    }
    if (!request.headers.get(ACCESS_ASSERTION_HEADER)?.trim()) {
      throw new ProxyRejection(
        403,
        'Cloudflare Access authentication required.',
      )
    }
  }
  if (SAFE_METHODS.has(method.toUpperCase())) return
  if (request.headers.get('sec-fetch-site')?.toLowerCase() === 'cross-site') {
    throw new ProxyRejection(403, 'Cross-site requests are not allowed.')
  }
  const origin = request.headers.get('origin')
  if (origin !== null) {
    let originHost: string
    try {
      originHost = new URL(origin).host.toLowerCase()
    } catch {
      throw new ProxyRejection(403, 'Request origin is not allowed.')
    }
    if (originHost !== host) {
      throw new ProxyRejection(403, 'Request origin is not allowed.')
    }
  }
}

function safeDecode(segment: string): string {
  try {
    return decodeURIComponent(segment)
  } catch {
    return segment
  }
}

/** Decode, validate and re-encode path segments so the upstream path cannot escape its prefix. */
export function sanitizePathSegments(path: string[]): string[] {
  return path.map((segment) => {
    const decoded = safeDecode(segment)
    if (
      decoded === '' ||
      decoded === '.' ||
      decoded === '..' ||
      /[/\\]/.test(decoded) ||
      // biome-ignore lint/suspicious/noControlCharactersInRegex: rejecting control characters is the point
      /[\u0000-\u001f\u007f]/.test(decoded)
    ) {
      throw new ProxyRejection(400, 'Invalid request path.')
    }
    return encodeURIComponent(decoded)
  })
}

export function buildUpstreamUrl(
  prefix: 'api' | 'health',
  path: string[],
  searchParams?: string,
): string {
  const joined = sanitizePathSegments(path).join('/')
  const qs = searchParams ? `?${searchParams}` : ''
  return `${getApiBaseUrl()}/${prefix}/${joined}${qs}`
}

export function buildForwardedHeaders(request: Request): Headers {
  const forwarded = new Headers()
  for (const name of FORWARDED_HEADER_ALLOWLIST) {
    const value = request.headers.get(name)
    if (value !== null) forwarded.set(name, value)
  }
  return forwarded
}

export async function readBoundedBody(
  request: Request,
  maxBytes: number = MAX_PROXY_BODY_BYTES,
): Promise<ArrayBuffer> {
  const tooLarge = () =>
    new ProxyRejection(
      413,
      `Request body must be ${Math.floor(maxBytes / (1024 * 1024))} MB or smaller.`,
    )
  const declared = request.headers.get('content-length')
  if (declared !== null) {
    if (!/^\d+$/.test(declared.trim())) {
      throw new ProxyRejection(400, 'Invalid Content-Length header.')
    }
    if (Number(declared) > maxBytes) throw tooLarge()
  }
  if (!request.body) return new ArrayBuffer(0)
  const reader = request.body.getReader()
  const chunks: Uint8Array[] = []
  let total = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    total += value.byteLength
    if (total > maxBytes) {
      await reader.cancel().catch(() => undefined)
      throw tooLarge()
    }
    chunks.push(value)
  }
  const body = new Uint8Array(total)
  let offset = 0
  for (const chunk of chunks) {
    body.set(chunk, offset)
    offset += chunk.byteLength
  }
  return body.buffer
}

export function proxyResponse(response: Response): Response {
  const headers = new Headers()
  headers.set(
    'Content-Type',
    response.headers.get('Content-Type') ?? 'application/json',
  )
  headers.set('Cache-Control', 'no-store, max-age=0')
  headers.set('Pragma', 'no-cache')
  headers.set('Expires', '0')
  const contentDisposition = response.headers.get('Content-Disposition')
  if (contentDisposition) {
    headers.set('Content-Disposition', contentDisposition)
  }
  return new Response(response.body, {
    status: response.status,
    headers,
  })
}

export type ProxyRouteContext = { params: Promise<{ path: string[] }> }

export async function proxyRequest(
  request: Request,
  { params }: ProxyRouteContext,
  prefix: 'api' | 'health',
  method: string,
): Promise<Response> {
  try {
    assertProxyRequestAllowed(request, method)
    const { path } = await params
    const url = buildUpstreamUrl(
      prefix,
      path,
      new URL(request.url).searchParams.toString(),
    )
    const body =
      method === 'GET' || method === 'HEAD'
        ? undefined
        : await readBoundedBody(request)
    const response = await fetch(url, {
      method,
      headers: buildForwardedHeaders(request),
      cache: 'no-store',
      ...(body && body.byteLength > 0 ? { body } : {}),
    })
    return proxyResponse(response)
  } catch (error) {
    if (error instanceof ProxyRejection) return rejectionResponse(error)
    throw error
  }
}
