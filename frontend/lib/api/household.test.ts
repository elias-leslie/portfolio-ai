import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  answerHouseholdQuestion,
  categorizeHouseholdTransaction,
  fetchHouseholdDashboard,
  uploadHouseholdDocument,
} from './household'

describe('household api', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('requests the household dashboard endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        generated_at: '2026-03-09T00:00:00Z',
        overview: {
          invested_assets: 0,
          retirement_assets: 0,
          taxable_assets: 0,
          cash_reserve: 0,
          total_tracked_assets: 0,
          visibility_score: 0,
          visibility_label: 'Early household setup',
          next_best_action: 'Upload recent statements.',
        },
        profile: {
          id: 'profile-1',
          household_name: 'Household',
          monthly_net_income_target: null,
          monthly_essential_target: null,
          monthly_discretionary_target: null,
          monthly_savings_target: null,
          target_retirement_age: null,
          target_retirement_spend: null,
          notes: null,
          created_at: '2026-03-09T00:00:00Z',
          updated_at: '2026-03-09T00:00:00Z',
        },
        resolved_values: [],
        budget_readiness: {
          status: 'setup_needed',
          summary: 'Needs setup',
          priorities: [],
          missing_inputs: [],
          starter_lanes: [],
        },
        budget_snapshot: {
          status: 'setup_needed',
          summary: 'Set the core monthly plan.',
          monthly_income_target: null,
          monthly_plan_total: null,
          essential_target: null,
          discretionary_target: null,
          savings_target: null,
          actual_monthly_spend: 0,
          actual_essential_monthly_spend: 0,
          actual_discretionary_monthly_spend: 0,
          remaining_cash_after_plan: null,
          discretionary_headroom: null,
        },
        retirement_preparedness: {
          status: 'baseline_visible',
          summary: 'Needs more data',
          retirement_account_share: 0,
          strengths: [],
          blockers: [],
          next_steps: [],
        },
        jenny_needs: [],
        categorization_queue: [],
        recurring_commitments: [],
        sinking_funds: [],
        retirement_contribution_tracker: {
          status: 'target_missing',
          monthly_target: null,
          estimated_monthly_contributions: 0,
          monthly_gap: 0,
          detail: 'Set a target.',
        },
        retirement_scenarios: [],
        import_center: {
          headline: 'Import things',
          tracked_documents: 0,
          parsed_documents: 0,
          suggested_first_uploads: [],
          automations: [],
          supported_documents: [],
        },
        questions: [],
        jenny_brief: {
          headline: 'Jenny',
          body: 'Body',
          prompts: [],
        },
        reports: {
          executive: {
            headline: 'Ledger ready',
            summary: 'Summary',
            average_monthly_spend: 0,
            average_monthly_essentials: 0,
            average_monthly_discretionary: 0,
            recent_30_day_spend: 0,
            recurring_merchant_count: 0,
            tracked_expense_count: 0,
            coverage_months: 0,
          },
          category_breakdown: [],
          merchant_highlights: [],
          monthly_spend_trend: [],
          recent_transactions: [],
        },
      }),
    }) as unknown as typeof fetch

    await fetchHouseholdDashboard()

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/household/dashboard',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('uploads a document as multipart form data', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        id: 'doc-1',
        filename: 'receipt.png',
        source_type: 'receipt',
        document_type: 'receipt',
        status: 'staged',
        account_label: null,
        file_size_bytes: 100,
        content_type: 'image/png',
        classification_confidence: 0.8,
        review_status: 'complete',
        review_summary: 'Reviewed',
        review_confidence: 0.8,
        statement_start: null,
        statement_end: null,
        uploaded_at: '2026-03-09T00:00:00Z',
        parsed_at: null,
        metadata: {},
      }),
    }) as unknown as typeof fetch

    const file = new File(['hello'], 'receipt.png', { type: 'image/png' })
    await uploadHouseholdDocument({ file, sourceType: 'receipt' })

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/household/documents',
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
      }),
    )
  })

  it('answers a household question', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        id: 'question-1',
        field_name: 'target_retirement_age',
        status: 'answered',
        priority: 'high',
        question: 'What age do you want to retire?',
        rationale: null,
        recommendation: 'Use age 60 unless you expect to work materially longer.',
        answer_text: '60',
        source_document_id: 'doc-1',
        question_format: 'integer',
        options: null,
        direction: 'jenny_to_user',
        metadata: {},
        created_at: '2026-03-09T00:00:00Z',
        answered_at: '2026-03-09T00:05:00Z',
      }),
    }) as unknown as typeof fetch

    await answerHouseholdQuestion('question-1', { answerText: '60' })

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/household/questions/question-1/answer',
      expect.objectContaining({
        method: 'POST',
      }),
    )
  })

  it('categorizes a household transaction', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({ ok: true }),
    }) as unknown as typeof fetch

    await categorizeHouseholdTransaction('txn-1', {
      category: 'Groceries',
      essentiality: 'essential',
    })

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/household/transactions/txn-1/categorize',
      expect.objectContaining({
        method: 'POST',
      }),
    )
  })
})
