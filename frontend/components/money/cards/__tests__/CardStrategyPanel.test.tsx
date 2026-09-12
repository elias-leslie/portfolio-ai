import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import type { BillSuggestion, StrategyView } from '@/lib/api/cards/strategy'
import { CardStrategyPanel } from '../CardStrategyPanel'
import { StrategyBillChecklist } from '../StrategyBillChecklist'

const mocks = vi.hoisted(() => ({
  query: vi.fn(),
  decision: vi.fn(),
  proposal: vi.fn(),
  bill: vi.fn(),
  billPreference: vi.fn(),
  error: null as Error | null,
}))
vi.mock('@/lib/hooks/useCardStrategy', () => ({
  useCardStrategy: () => mocks.query(),
  useStrategyActions: () => ({
    proposal: { mutate: mocks.proposal, isPending: false },
    decision: { mutate: mocks.decision, isPending: false, error: mocks.error },
    bill: { mutate: mocks.bill, isPending: false },
    billPreference: { mutate: mocks.billPreference, isPending: false },
  }),
}))
vi.mock('../StrategyPreferences', () => ({ StrategyPreferences: () => null }))
vi.mock('../CardBonusControls', () => ({ CardBonusControls: () => null }))

function view(): StrategyView {
  const settings = {
    remindersEnabled: true,
    automaticResearch: false,
    reserveAmazon: true,
    reserveCostco: true,
    reserveGas: true,
    monthlyCap: null,
    costcoMonthly: 900,
  }
  const baseline = {
    monthlyAvailable: 1800,
    historicalMonthly: 2700,
    months: [],
    incomeMonthly: 3500,
    incomeSource: 'Deposits',
    freeCash: 8000,
    cashStatus: 'estimate',
    reservations: [],
    warnings: ['Recent transactions need updating.'],
  }
  const candidate = {
    key: 'product:p2',
    productId: 'product',
    productName: 'Travel card',
    player: 'p2',
    applicant: 'Mariana',
    applicationOn: '2026-09-12',
    applicationBy: '2026-09-26',
    minimumSpend: 4000,
    windowDays: 90,
    bonusValue: 750,
    annualFee: 95,
    incrementalValue: 655,
    monthlyRequired: 1353,
    termsFingerprint: 'terms',
    termsCurrent: true,
    sourceUrls: ['https://www.capitalone.com/credit-cards/venture/'],
    checks: ['Confirm eligibility'],
    rationale: 'Ordinary spending covers the requirement.',
    spendingGap: 0,
    monthlyGap: 0,
    valueRank: 1,
    comparedOffers: 1,
    catalogOffers: 4,
  }
  const draft = {
    id: 'draft',
    fingerprint: 'snapshot',
    status: 'draft',
    actualCardId: null,
    createdAt: '2026-09-12',
    approvedAt: null,
    eligibilityConfirmed: false,
    snapshot: {
      settings,
      baseline,
      candidate,
      bills: [],
      recommendation: 'One bonus at a time',
      additionalSpendPlan: null,
    },
  }
  return {
    asOf: '2026-09-12',
    settings,
    baseline,
    candidates: [candidate],
    recommendation: 'One bonus at a time',
    active: null,
    draft,
    history: [draft],
    progress: [],
    bills: [],
    changes: [],
    reviewEvents: [],
  }
}
const bill: BillSuggestion = {
  key: 'phone',
  merchant: 'Phone',
  amount: 100,
  cadence: 'monthly',
  nextExpected: '2026-10-01',
  firstChargeDueOn: null,
  currentAccount: 'Old bank',
  alreadyCardSpend: false,
  evidence: 'Three monthly charges',
  status: 'suggested',
  paidFromCma: false,
  paymentPreference: 'automatic',
  keepCurrentPayment: false,
  paymentReason: null,
  feePerCharge: 0,
  lostDiscount: 0,
  observedOn: null,
  observationId: null,
}

beforeEach(() => {
  mocks.decision.mockReset()
  mocks.proposal.mockReset()
  mocks.bill.mockReset()
  mocks.billPreference.mockReset()
  mocks.error = null
  mocks.query.mockReturnValue({
    data: view(),
    isError: false,
    isLoading: false,
  })
})

it('requires both financial assumptions and applicant eligibility before exact draft approval', async () => {
  const user = userEvent.setup()
  render(<CardStrategyPanel cards={[]} onAddCard={vi.fn()} />)
  const approve = screen.getByRole('button', { name: 'Approve this strategy' })
  expect(approve).toBeDisabled()
  await user.click(
    screen.getByRole('checkbox', { name: /complete card history/ }),
  )
  expect(approve).toBeDisabled()
  await user.click(
    screen.getByRole('checkbox', {
      name: /can pay these ordinary purchases in full/,
    }),
  )
  await user.click(approve)
  expect(mocks.decision).toHaveBeenCalledExactlyOnceWith({
    id: 'draft',
    payload: {
      action: 'approve',
      fingerprint: 'snapshot',
      eligibilityConfirmed: true,
      cashFlowConfirmed: true,
    },
  })
})

it('cannot approve unsupported issuer evidence even with both confirmations', async () => {
  const data = view()
  if (data.draft?.snapshot.candidate)
    data.draft.snapshot.candidate.termsCurrent = false
  mocks.query.mockReturnValue({ data })
  const user = userEvent.setup()
  render(<CardStrategyPanel cards={[]} onAddCard={vi.fn()} />)
  for (const checkbox of screen.getAllByRole('checkbox'))
    await user.click(checkbox)
  expect(
    screen.getByRole('button', { name: 'Approve this strategy' }),
  ).toBeDisabled()
  expect(mocks.decision).not.toHaveBeenCalled()
})

it('shows stale approval failure without presenting an approved plan', () => {
  mocks.error = new Error('Offer changed. Create a fresh draft.')
  render(<CardStrategyPanel cards={[]} onAddCard={vi.fn()} />)
  expect(screen.getAllByRole('alert')[0]).toHaveTextContent('Offer changed')
  expect(screen.queryByText('Approved plan')).not.toBeInTheDocument()
})

it('records a bill change only after explicit acceptance, benefit checks, and costs', async () => {
  const user = userEvent.setup()
  render(<StrategyBillChecklist bills={[bill]} planId="plan" enabled />)
  await user.click(
    screen.getByRole('button', { name: 'Review payment change' }),
  )
  expect(
    screen.getByRole('button', { name: 'Confirm payment change' }),
  ).toBeDisabled()
  for (const checkbox of screen.getAllByRole('checkbox'))
    await user.click(checkbox)
  await user.type(screen.getByLabelText('Fee per charge'), '0')
  await user.type(screen.getByLabelText('Lost discount per charge'), '0')
  await user.click(
    screen.getByRole('button', { name: 'Confirm payment change' }),
  )
  expect(mocks.bill).toHaveBeenCalledWith(
    {
      id: 'plan',
      key: 'phone',
      payload: {
        status: 'confirmed',
        cardAccepted: true,
        benefitsChecked: true,
        feePerCharge: 0,
        lostDiscount: 0,
      },
    },
    expect.anything(),
  )
})

it('distinguishes a recorded payment change from an observed posted charge', () => {
  render(
    <StrategyBillChecklist
      bills={[{ ...bill, status: 'confirmed' }]}
      planId="plan"
      enabled
    />,
  )
  expect(
    screen.getByText('Changed · awaiting first charge'),
  ).toBeInTheDocument()
  expect(screen.queryByText('First charge verified')).not.toBeInTheDocument()
})

it('lets a CMA bill be an exception before a plan exists without confirming a payment change', async () => {
  const user = userEvent.setup()
  render(
    <StrategyBillChecklist
      bills={[
        {
          ...bill,
          currentAccount: 'CMA',
          paidFromCma: true,
          keepCurrentPayment: true,
          status: 'kept_in_place',
          feePerCharge: null,
          lostDiscount: null,
          paymentReason:
            'Paid from your CMA; kept here under your card-fee preference.',
        },
      ]}
      planId={null}
      enabled={false}
    />,
  )
  expect(screen.getByText('Keep in place')).toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: 'Review payment change' }),
  ).not.toBeInTheDocument()
  await user.selectOptions(
    screen.getByLabelText('Payment preference'),
    'consider_card',
  )
  expect(mocks.billPreference).toHaveBeenCalledExactlyOnceWith({
    key: 'phone',
    preference: 'consider_card',
  })
  expect(mocks.bill).not.toHaveBeenCalled()
})

it('keeps a CMA bill out of payment-change actions even with an approved linked card', () => {
  render(
    <StrategyBillChecklist
      bills={[
        {
          ...bill,
          paidFromCma: true,
          keepCurrentPayment: true,
          status: 'kept_in_place',
        },
      ]}
      planId="plan"
      enabled
    />,
  )
  expect(
    screen.queryByRole('button', { name: 'Review payment change' }),
  ).not.toBeInTheDocument()
  expect(screen.getByLabelText('Payment preference')).toBeEnabled()
})

it('lets an exception return to the automatic CMA rule', async () => {
  const user = userEvent.setup()
  render(
    <StrategyBillChecklist
      bills={[
        {
          ...bill,
          paidFromCma: true,
          paymentPreference: 'consider_card',
        },
      ]}
      planId="plan"
      enabled
    />,
  )
  expect(
    screen.getByRole('button', { name: 'Review payment change' }),
  ).toBeEnabled()
  await user.selectOptions(
    screen.getByLabelText('Payment preference'),
    'automatic',
  )
  expect(mocks.billPreference).toHaveBeenCalledExactlyOnceWith({
    key: 'phone',
    preference: 'automatic',
  })
})

it('compares higher-spend alternatives beside the proposal and requires a purchase plan', async () => {
  const data = view()
  data.candidates.push({
    ...data.candidates[0],
    key: 'stretch:p2',
    productId: 'stretch',
    productName: 'Higher-value card',
    spendingGap: 400,
    monthlyGap: 146.69,
    minimumSpend: 5400,
    incrementalValue: 900,
    valueRank: 1,
    comparedOffers: 2,
  })
  data.candidates[0].valueRank = 2
  data.candidates[0].comparedOffers = 2
  mocks.query.mockReturnValue({ data })
  const user = userEvent.setup()
  render(<CardStrategyPanel cards={[]} onAddCard={vi.fn()} />)
  const proposal = within(
    screen.getByRole('region', { name: 'Proposed card strategy' }),
  )
  await user.click(
    proposal.getByRole('button', { name: 'Value #2 of 2 checked offers' }),
  )
  expect(
    proposal.getByText(/not every market or personalized offer/),
  ).toBeInTheDocument()
  expect(proposal.getByText(/Needs \$400.00 more in total/)).toBeInTheDocument()
  await user.click(
    proposal.getByRole('button', { name: 'Review Higher-value card' }),
  )
  expect(mocks.proposal).not.toHaveBeenCalled()
  const prepare = proposal.getByRole('button', {
    name: 'Prepare this higher-spend proposal',
  })
  expect(prepare).toBeDisabled()
  await user.type(
    proposal.getByRole('textbox'),
    'Already-budgeted annual insurance renewal',
  )
  await user.click(prepare)
  expect(mocks.proposal).toHaveBeenCalledExactlyOnceWith({
    key: 'stretch:p2',
    additionalSpendPlan: 'Already-budgeted annual insurance renewal',
  })
})

it('requires explicit approval of extra purchases in a higher-spend draft', async () => {
  const data = view()
  if (!data.draft?.snapshot.candidate)
    throw new Error('Missing fixture candidate')
  data.draft.snapshot.candidate.spendingGap = 400
  data.draft.snapshot.additionalSpendPlan = 'Annual insurance renewal'
  mocks.query.mockReturnValue({ data })
  const user = userEvent.setup()
  render(<CardStrategyPanel cards={[]} onAddCard={vi.fn()} />)
  await user.click(
    screen.getByRole('checkbox', { name: /complete card history/ }),
  )
  await user.click(
    screen.getByRole('checkbox', {
      name: /can pay these ordinary purchases in full/,
    }),
  )
  expect(
    screen.getByRole('button', { name: 'Approve this strategy' }),
  ).toBeDisabled()
  await user.click(
    screen.getByRole('checkbox', {
      name: /additional purchases are already planned/,
    }),
  )
  await user.click(
    screen.getByRole('button', { name: 'Approve this strategy' }),
  )
  expect(mocks.decision).toHaveBeenCalledWith(
    expect.objectContaining({
      payload: expect.objectContaining({ additionalSpendConfirmed: true }),
    }),
  )
})

it('blocks a saved draft when current offer evidence is no longer verified', async () => {
  const data = view()
  data.candidates = [{ ...data.candidates[0], termsCurrent: false }]
  mocks.query.mockReturnValue({ data })
  const user = userEvent.setup()
  render(<CardStrategyPanel cards={[]} onAddCard={vi.fn()} />)
  await user.click(
    screen.getByRole('checkbox', { name: /complete card history/ }),
  )
  await user.click(
    screen.getByRole('checkbox', {
      name: /can pay these ordinary purchases in full/,
    }),
  )
  expect(
    screen.getByRole('button', { name: 'Approve this strategy' }),
  ).toBeDisabled()
  expect(
    screen.getByText(/Current offer or spending evidence changed/),
  ).toBeInTheDocument()
})
