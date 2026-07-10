import { createRemoteJWKSet, jwtVerify } from 'jose'
import { type NextRequest, NextResponse } from 'next/server'

const accessHeader = 'cf-access-jwt-assertion'
const teamDomain = (
  process.env.CLOUDFLARE_ACCESS_TEAM_DOMAIN ?? 'summitflow.cloudflareaccess.com'
).replace(/^https?:\/\//, '')
const issuer = `https://${teamDomain}`
const accessKeys = createRemoteJWKSet(new URL(`${issuer}/cdn-cgi/access/certs`))

function isLocalHostname(hostname: string): boolean {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname === '::1' ||
    hostname.endsWith('.localhost')
  )
}

async function hasValidAccessAssertion(request: NextRequest): Promise<boolean> {
  const assertion = request.headers.get(accessHeader)?.trim() ?? ''
  if (assertion.split('.').length !== 3) return false

  try {
    const audience = process.env.CLOUDFLARE_ACCESS_AUD?.trim()
    const { payload } = await jwtVerify(assertion, accessKeys, {
      issuer,
      ...(audience ? { audience } : {}),
    })
    return typeof payload.email === 'string' && payload.email.length > 0
  } catch {
    return false
  }
}

function requestHostname(request: NextRequest): string {
  const host = request.headers.get('host') ?? request.nextUrl.host
  if (host.startsWith('[')) return host.slice(1, host.indexOf(']'))
  return host.split(':', 1)[0] ?? ''
}

/** Fail closed when a non-local request reaches Next without Cloudflare Access. */
export async function middleware(request: NextRequest) {
  if (isLocalHostname(requestHostname(request))) {
    return NextResponse.next()
  }

  if (await hasValidAccessAssertion(request)) return NextResponse.next()

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
