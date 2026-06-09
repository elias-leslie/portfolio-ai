import { type ProxyRouteContext, proxyRequest } from '@/lib/upstream-proxy'

export const runtime = 'nodejs'

export async function GET(request: Request, context: ProxyRouteContext) {
  return proxyRequest(request, context, 'health', 'GET')
}

export async function POST(request: Request, context: ProxyRouteContext) {
  return proxyRequest(request, context, 'health', 'POST')
}
