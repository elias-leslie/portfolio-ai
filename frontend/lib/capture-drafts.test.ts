import { afterEach, describe, expect, it, vi } from 'vitest'
import { type CaptureDraft, uploadCaptureDraft } from './capture-drafts'

const draft: CaptureDraft = {
  id: 'draft-test',
  member: 'member-a',
  kind: 'shelf_tag',
  file: new Blob(['test'], { type: 'image/jpeg' }),
  filename: 'tag.jpg',
  storeName: 'Test store',
  note: 'Test note',
  createdAt: 1,
}

describe('capture upload recovery', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('keeps drafts on an interrupted upload and reuses their identity on retry', async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError('offline'))
    vi.stubGlobal('fetch', fetch)
    const indexedDB = { open: vi.fn() }
    vi.stubGlobal('indexedDB', indexedDB)
    await expect(uploadCaptureDraft(draft)).rejects.toThrow('offline')
    await expect(uploadCaptureDraft(draft)).rejects.toThrow('offline')
    expect(indexedDB.open).not.toHaveBeenCalled()
    for (const call of fetch.mock.calls) {
      const data = call[1].body as FormData
      expect(data.get('client_id')).toBe(draft.id)
      expect(data.get('member_scope')).toBe('member-a')
      expect(data.has('purchased_by')).toBe(false)
      expect(data.has('outcome')).toBe(false)
    }
  })

  it('does not delete a draft after a sign-in or ownership failure', async () => {
    const indexedDB = { open: vi.fn() }
    vi.stubGlobal('indexedDB', indexedDB)
    for (const status of [403, 409, 503]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status }))
      await expect(uploadCaptureDraft(draft)).rejects.toThrow(/sign.in/i)
    }
    expect(indexedDB.open).not.toHaveBeenCalled()
  })
})
