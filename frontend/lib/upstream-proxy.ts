const API_BASE_URL = process.env.API_URL || 'http://localhost:8000'

export function buildUpstreamUrl(
  prefix: 'api' | 'health',
  path: string[],
  searchParams?: string,
): string {
  const joined = path.join('/')
  const qs = searchParams ? `?${searchParams}` : ''
  return `${API_BASE_URL}/${prefix}/${joined}${qs}`
}

export function proxyResponse(response: Response): Response {
  return new Response(response.body, {
    status: response.status,
    headers: {
      'Content-Type':
        response.headers.get('Content-Type') ?? 'application/json',
    },
  })
}

type ProxyRouteContext = { params: Promise<{ path: string[] }> }

export async function proxyRequest(
  request: Request,
  { params }: ProxyRouteContext,
  prefix: 'api' | 'health',
  method: string,
): Promise<Response> {
  const { path } = await params
  const url = buildUpstreamUrl(
    prefix,
    path,
    new URL(request.url).searchParams.toString(),
  )
  const body =
    method === 'GET' || method === 'HEAD' ? undefined : await request.text()
  const forwardedHeaders = new Headers(request.headers)
  forwardedHeaders.delete('host')
  const response = await fetch(url, {
    method,
    headers: forwardedHeaders,
    ...(body ? { body } : {}),
  })
  return proxyResponse(response)
}
