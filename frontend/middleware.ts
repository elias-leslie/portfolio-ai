import { type NextRequest, NextResponse } from 'next/server'

const accessHeader = 'cf-access-jwt-assertion'
function isLocalHostname(hostname: string): boolean {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname === '::1' ||
    hostname.endsWith('.localhost')
  )
}

function requestHostname(request: NextRequest): string {
  const host = request.headers.get('host') ?? request.nextUrl.host
  if (host.startsWith('[')) return host.slice(1, host.indexOf(']'))
  return host.split(':', 1)[0] ?? ''
}

/** Fail closed when a non-local request reaches Next without Cloudflare Access. */
export async function middleware(request: NextRequest) {
  if (
    isLocalHostname(requestHostname(request)) &&
    !request.headers.has(accessHeader) &&
    !request.headers.has('cf-ray')
  ) {
    return NextResponse.next()
  }

  // Every API request is authorized at the backend, including capture-only roles.
  if (request.nextUrl.pathname.startsWith('/api/')) return NextResponse.next()

  if (request.headers.get(accessHeader)) {
    try {
      const response = await fetch(
        `${process.env.API_URL || 'http://localhost:8000'}/api/identity`,
        {
          headers: { [accessHeader]: request.headers.get(accessHeader) ?? '' },
          cache: 'no-store',
        },
      )
      if (!response.ok)
        return new NextResponse(
          'Household sign-in is unavailable or this member is not registered.',
          { status: response.status, headers: { 'Cache-Control': 'no-store' } },
        )
      const identity: unknown = await response.json()
      if (
        typeof identity !== 'object' ||
        identity === null ||
        !('access' in identity)
      )
        throw new Error('Invalid identity')
      if (
        identity.access === 'capture_only' &&
        !request.nextUrl.pathname.startsWith('/api/') &&
        request.nextUrl.pathname !== '/capture'
      ) {
        return NextResponse.redirect(new URL('/capture', request.url))
      }
      return NextResponse.next()
    } catch {
      return new NextResponse(
        'Unable to verify household access. Please retry.',
        { status: 503, headers: { 'Cache-Control': 'no-store' } },
      )
    }
  }

  return new NextResponse('Cloudflare Access authentication required.', {
    status: 403,
    headers: { 'Cache-Control': 'no-store' },
  })
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|icons/|manifest.json|sw.js).*)',
  ],
}
