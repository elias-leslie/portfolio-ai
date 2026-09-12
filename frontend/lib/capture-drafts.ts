/** Only camera drafts live offline. Financial responses are never cached here. */
export type CaptureDraft = {
  id: string
  member: string
  kind: 'receipt' | 'shelf_tag'
  file: Blob
  filename: string
  storeName: string
  note: string
  createdAt: number
  error?: string
}

const databaseName = 'portfolio-ai-capture-drafts'
const storeName = 'drafts'
function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(databaseName, 1)
    request.onupgradeneeded = () =>
      request.result.createObjectStore(storeName, { keyPath: 'id' })
    request.onsuccess = () => resolve(request.result)
    request.onerror = () =>
      reject(
        new Error(
          'This browser could not save a local draft. Keep the photo and retry.',
        ),
      )
  })
}

async function writeDraft(
  action: (store: IDBObjectStore) => void,
): Promise<void> {
  const db = await openDatabase()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(storeName, 'readwrite')
      transaction.oncomplete = () => resolve()
      transaction.onabort = transaction.onerror = () =>
        reject(
          new Error(
            'The draft could not be saved on this device. Keep the original photo.',
          ),
        )
      action(transaction.objectStore(storeName))
    })
  } finally {
    db.close()
  }
}

export const saveCaptureDraft = (draft: CaptureDraft) =>
  writeDraft((store) => store.put(draft))
export const removeCaptureDraft = (id: string) =>
  writeDraft((store) => store.delete(id))
export async function listCaptureDrafts(
  member: string,
): Promise<CaptureDraft[]> {
  const db = await openDatabase()
  try {
    const rows = await new Promise<CaptureDraft[]>((resolve, reject) => {
      const request = db.transaction(storeName).objectStore(storeName).getAll()
      request.onsuccess = () => resolve(request.result as CaptureDraft[])
      request.onerror = () =>
        reject(
          new Error(
            'Saved drafts could not be read. Retry without clearing browser storage.',
          ),
        )
    })
    return rows
      .filter((row) => row.member === member)
      .sort((a, b) => a.createdAt - b.createdAt)
  } finally {
    db.close()
  }
}

export async function uploadCaptureDraft(draft: CaptureDraft): Promise<void> {
  const data = new FormData()
  data.set('file', draft.file, draft.filename)
  data.set('client_id', draft.id)
  data.set('member_scope', draft.member)
  data.set('kind', draft.kind)
  data.set('store_name', draft.storeName)
  data.set('note', draft.note)
  const response = await fetch('/api/captures', { method: 'POST', body: data })
  if (!response.ok) {
    if (response.status === 409)
      throw new Error(
        'This draft belongs to a different sign-in or conflicts with an earlier upload. Switch back to its member; keep the draft.',
      )
    if (response.status === 403 || response.status === 503)
      throw new Error(
        'Sign in again, then retry. The draft is still on this device.',
      )
    if (response.status === 413)
      throw new Error('The photo is too large. Use a file smaller than 15 MB.')
    if (response.status === 415)
      throw new Error('Use a JPEG, PNG or WebP photo, or a PDF receipt.')
    throw new Error(
      'Upload did not finish. The draft is saved; retry when connected.',
    )
  }
  await removeCaptureDraft(draft.id)
}
