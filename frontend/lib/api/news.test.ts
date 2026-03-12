import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchArticleFeedback, submitArticleFeedback } from './news'

describe('news api helpers', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('fetches existing article feedback and camel-cases the payload', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        exists: true,
        is_useful: true,
        created_at: '2026-03-12T12:00:00Z',
      }),
    }) as unknown as typeof fetch

    const result = await fetchArticleFeedback('aapl-hash')

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/news/article-feedback/aapl-hash',
      expect.objectContaining({
        method: 'GET',
      }),
    )
    expect(result).toEqual({
      exists: true,
      isUseful: true,
      createdAt: '2026-03-12T12:00:00Z',
    })
  })

  it('posts article feedback using snake_case fields', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        status: 'success',
        message: 'saved',
        vendor: 'rss',
        updated_useful_rate: 0.8,
      }),
    }) as unknown as typeof fetch

    const result = await submitArticleFeedback({
      articleUrl: 'https://example.com/aapl',
      articleHash: 'aapl-hash',
      vendor: 'rss',
      isUseful: true,
    })

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/news/article-feedback',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          article_url: 'https://example.com/aapl',
          article_hash: 'aapl-hash',
          vendor: 'rss',
          is_useful: true,
        }),
      }),
    )
    expect(result).toEqual({
      status: 'success',
      message: 'saved',
      vendor: 'rss',
      updatedUsefulRate: 0.8,
    })
  })
})
