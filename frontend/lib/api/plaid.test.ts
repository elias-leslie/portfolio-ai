import { describe, expect, it } from 'vitest'
import { plaidSyncIssues } from './plaid'

const base = {
  itemCount: 1,
  accountCount: 2,
  transactionAddedCount: 0,
  transactionModifiedCount: 0,
  transactionRemovedCount: 0,
}

describe('plaidSyncIssues', () => {
  it('returns null for a clean sync', () => {
    expect(plaidSyncIssues({ ...base, errors: [], skipped: [] })).toBeNull()
  })

  it('reports items skipped because another sync is running', () => {
    const issues = plaidSyncIssues({
      ...base,
      errors: [],
      skipped: [{ item_id: 'a', reason: 'sync_in_progress' }],
    })
    expect(issues?.count).toBe(1)
    expect(issues?.description).toContain('already running')
  })

  it('prefers item errors over skipped items', () => {
    const issues = plaidSyncIssues({
      ...base,
      errors: [{ error_message: 'Login required' }],
      skipped: [{ item_id: 'b' }],
    })
    expect(issues).toEqual({ count: 1, description: 'Login required' })
  })
})
