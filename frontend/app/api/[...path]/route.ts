import { type ProxyRouteContext, proxyRequest } from '@/lib/upstream-proxy'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const revalidate = 0
export const fetchCache = 'force-no-store'

export async function GET(request: Request, context: ProxyRouteContext) {
  return proxyRequest(request, context, 'api', 'GET')
}

export async function POST(request: Request, context: ProxyRouteContext) {
  return proxyRequest(request, context, 'api', 'POST')
}

export async function PUT(request: Request, context: ProxyRouteContext) {
  return proxyRequest(request, context, 'api', 'PUT')
}

export async function PATCH(request: Request, context: ProxyRouteContext) {
  return proxyRequest(request, context, 'api', 'PATCH')
}

export async function DELETE(request: Request, context: ProxyRouteContext) {
  return proxyRequest(request, context, 'api', 'DELETE')
}
