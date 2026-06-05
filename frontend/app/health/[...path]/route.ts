import { proxyRequest } from '@/lib/upstream-proxy'

export const runtime = 'nodejs'

type RouteContext = { params: Promise<{ path: string[] }> }

export async function GET(request: Request, context: RouteContext) {
  return proxyRequest(request, context, 'health', 'GET')
}

export async function POST(request: Request, context: RouteContext) {
  return proxyRequest(request, context, 'health', 'POST')
}
