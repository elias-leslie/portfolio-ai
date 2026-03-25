'use client'

import { useEffect, useMemo, useReducer } from 'react'
import type { HouseholdFinanceDashboard, HouseholdPlanningUpdate } from '@/lib/api/household'
import type {
  HouseholdDebtObligationInput,
  HouseholdHousingCostInput,
  HouseholdIncomeSourceInput,
  HouseholdInsurancePolicyInput,
  HouseholdPlannedExpenseInput,
  HouseholdPlanningMemberInput,
  HouseholdRetirementIncomeSourceInput,
} from '@/lib/api/household-planning'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { useUpdateHouseholdPlanning } from '@/lib/hooks/useHousehold'
import { formatCurrency, formatEnumLabel } from './formatters'
import { HouseholdPlanningDocumentsCard } from './household-planning-documents-card'
import {
  EditableListSection,
  type EditableItem,
  emptyPlanning,
  normalizeEditableItems,
  stripPlanningMeta,
} from './household-planning-editor'

function statusBadge(status: string) {
  switch (status) {
    case 'ready':
    case 'received':
      return 'success' as const
    case 'missing':
      return 'outline' as const
    default:
      return 'secondary' as const
  }
}

function toEditableItems<T extends { id?: string | null }>(items: T[]): EditableItem[] {
  return items.map((item) => ({ ...item }))
}

function normalizeSection<T>(items: EditableItem[], numericKeys: string[]): T[] {
  return normalizeEditableItems(items, numericKeys) as T[]
}

/* ── Editable-section reducer ─────────────────────────────────────────── */

type SectionKey =
  | 'members'
  | 'incomeSources'
  | 'debtObligations'
  | 'housingCosts'
  | 'insurancePolicies'
  | 'retirementIncomeSources'
  | 'plannedExpenses'

type SectionsState = Record<SectionKey, EditableItem[]>

type SectionsAction =
  | { type: 'RESET_ALL'; payload: SectionsState }
  | { type: 'UPDATE_DRAFT'; section: SectionKey; items: EditableItem[] }
  | {
      type: 'ADD_ITEM'
      section: SectionKey
      template: EditableItem
    }

function sectionsReducer(state: SectionsState, action: SectionsAction): SectionsState {
  switch (action.type) {
    case 'RESET_ALL':
      return action.payload
    case 'UPDATE_DRAFT':
      return { ...state, [action.section]: action.items }
    case 'ADD_ITEM':
      return { ...state, [action.section]: [...state[action.section], action.template] }
  }
}

function buildSectionsState(planning: ReturnType<typeof emptyPlanning>): SectionsState {
  return {
    members: toEditableItems(planning.members.map(stripPlanningMeta)),
    incomeSources: toEditableItems(planning.incomeSources.map(stripPlanningMeta)),
    debtObligations: toEditableItems(planning.debtObligations.map(stripPlanningMeta)),
    housingCosts: toEditableItems(planning.housingCosts.map(stripPlanningMeta)),
    insurancePolicies: toEditableItems(planning.insurancePolicies.map(stripPlanningMeta)),
    retirementIncomeSources: toEditableItems(planning.retirementIncomeSources.map(stripPlanningMeta)),
    plannedExpenses: toEditableItems(planning.plannedExpenses.map(stripPlanningMeta)),
  }
}

/* ── Component ────────────────────────────────────────────────────────── */

export function HouseholdPlanningPanels({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const planning = useMemo(() => dashboard.planning ?? emptyPlanning(), [dashboard.planning])
  const updatePlanning = useUpdateHouseholdPlanning()

  const [sections, dispatch] = useReducer(sectionsReducer, planning, (p) => buildSectionsState(p))

  useEffect(() => {
    dispatch({ type: 'RESET_ALL', payload: buildSectionsState(planning) })
  }, [planning])

  const saveSection = (payload: HouseholdPlanningUpdate) => {
    updatePlanning.mutate(payload)
  }

  const planningSections = planning.summary.sections

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <SectionCard
          variant="surface"
          title="Planning Coverage"
          description="How much of the household planning graph is already structured."
        >
          <p className="text-3xl font-semibold text-text">{planning.summary.completionScore}%</p>
          <p className="mt-2 text-sm text-text-muted">
            {planning.summary.readySections} of {planning.summary.totalSections} core sections are structured.
          </p>
        </SectionCard>
        <SectionCard
          variant="surface"
          title="Missing Documents"
          description="Planning placeholders Jenny is still waiting on."
        >
          <p className="text-3xl font-semibold text-text">{planning.summary.missingDocumentCount}</p>
          <p className="mt-2 text-sm text-text-muted">
            {planning.summary.highPriorityDocumentCount} high-priority document gap
            {planning.summary.highPriorityDocumentCount === 1 ? '' : 's'}.
          </p>
        </SectionCard>
        <SectionCard
          variant="surface"
          title="Section Status"
          description="What is complete versus still too thin for serious planning."
        >
          <div className="space-y-2">
            {planningSections.length === 0 ? (
              <p className="text-sm text-text-muted">Jenny has not scored the planning workbook yet.</p>
            ) : (
              planningSections.slice(0, 4).map((section) => (
                <div key={section.section} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-text">{section.label}</span>
                  <Badge variant={statusBadge(section.status)}>{formatEnumLabel(section.status)}</Badge>
                </div>
              ))
            )}
          </div>
        </SectionCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <SectionCard
          variant="surface"
          title="Budget Readiness"
          description={dashboard.budgetReadiness.summary}
        >
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <p className="text-sm font-semibold text-text">Missing inputs</p>
              <div className="mt-3 space-y-2">
                {dashboard.budgetReadiness.missingInputs.length === 0 ? (
                  <p className="text-sm text-text-muted">Jenny has the core budget inputs she needs.</p>
                ) : (
                  dashboard.budgetReadiness.missingInputs.map((item) => (
                    <p key={item} className="text-sm text-text-muted">
                      {item}
                    </p>
                  ))
                )}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-text">Starter lanes</p>
              <div className="mt-3 space-y-3">
                {dashboard.budgetReadiness.starterLanes.length === 0 ? (
                  <p className="text-sm text-text-muted">
                    No starter lanes yet. Jenny will suggest these once more recurring spend patterns are confirmed.
                  </p>
                ) : (
                  dashboard.budgetReadiness.starterLanes.map((lane) => (
                    <div key={lane.name} className="rounded-xl border border-border/40 bg-surface-muted/20 p-3">
                      <p className="text-sm font-semibold text-text">{lane.name}</p>
                      <p className="mt-1 text-sm text-text-muted">{lane.objective}</p>
                      <p className="mt-2 text-xs uppercase tracking-wide text-primary">{lane.status}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          variant="surface"
          title="Retirement Preparedness"
          description={dashboard.retirementPreparedness.summary}
        >
          <div className="space-y-5">
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-sm font-semibold text-text">Contribution tracker</p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {dashboard.retirementContributionTracker.monthlyTarget
                  ? formatCurrency(dashboard.retirementContributionTracker.monthlyGap)
                  : '—'}
              </p>
              <p className="mt-2 text-sm text-text-muted">
                {dashboard.retirementContributionTracker.detail}
              </p>
            </div>

            <div>
              <p className="text-sm font-semibold text-text">Strengths</p>
              <div className="mt-3 space-y-2">
                {dashboard.retirementPreparedness.strengths.length === 0 ? (
                  <p className="text-sm text-text-muted">
                    Jenny has not identified a strong retirement edge yet.
                  </p>
                ) : (
                  dashboard.retirementPreparedness.strengths.map((item, index) => (
                    <p key={`${item}-${index}`} className="text-sm text-text-muted">
                      {item}
                    </p>
                  ))
                )}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-text">Blockers</p>
              <div className="mt-3 space-y-2">
                {dashboard.retirementPreparedness.blockers.length === 0 ? (
                  <p className="text-sm text-text-muted">
                    No retirement blockers are flagged right now.
                  </p>
                ) : (
                  dashboard.retirementPreparedness.blockers.map((item, index) => (
                    <p key={`${item}-${index}`} className="text-sm text-text-muted">
                      {item}
                    </p>
                  ))
                )}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-text">Next steps</p>
              <div className="mt-3 space-y-2">
                {dashboard.retirementPreparedness.nextSteps.length === 0 ? (
                  <p className="text-sm text-text-muted">
                    Jenny does not have a next-step recommendation yet.
                  </p>
                ) : (
                  dashboard.retirementPreparedness.nextSteps.map((item, index) => (
                    <p key={`${item}-${index}`} className="text-sm text-text-muted">
                      {item}
                    </p>
                  ))
                )}
              </div>
            </div>

            <div>
              <p className="text-sm font-semibold text-text">Retirement scenarios</p>
              <div className="mt-3 space-y-3">
                {dashboard.retirementScenarios.length === 0 ? (
                  <p className="text-sm text-text-muted">
                    Retirement scenarios will appear once Jenny has enough spending and contribution evidence.
                  </p>
                ) : (
                  dashboard.retirementScenarios.map((scenario) => (
                    <div
                      key={scenario.name}
                      className="rounded-2xl border border-border/40 bg-surface/60 p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-text">{scenario.name}</p>
                          <p className="mt-1 text-sm text-text-muted">{scenario.detail}</p>
                        </div>
                        <div className="text-right text-sm">
                          <p className="font-semibold text-text">
                            {formatCurrency(scenario.monthlySpend)}
                          </p>
                          <p className="text-text-muted">{scenario.fundedYears} years funded</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard
        variant="surface"
        title="Planning Workbook"
        description="Maintain the durable household planning record Jenny uses for budgeting, retirement, taxes, debt, and future expenses."
      >
        <div className="grid gap-4 xl:grid-cols-2">
          <EditableListSection
            title="Household members"
            description="Adults, kids, and other dependents that shape cash flow and goals."
            fields={[
              { key: 'displayName', label: 'Name', placeholder: 'Alex' },
              { key: 'role', label: 'Role', placeholder: 'adult or child' },
              { key: 'relationship', label: 'Relationship', placeholder: 'spouse, son, parent' },
              { key: 'birthYear', label: 'Birth year', placeholder: '2018', inputMode: 'numeric' },
            ]}
            items={sections.members}
            onChange={(items) =>
              dispatch({ type: 'UPDATE_DRAFT', section: 'members', items })
            }
            onAdd={() =>
              dispatch({
                type: 'ADD_ITEM',
                section: 'members',
                template: { displayName: '', role: '', relationship: '', birthYear: null },
              })
            }
            onSave={() =>
              saveSection({
                members: normalizeSection<HouseholdPlanningMemberInput>(sections.members, ['birthYear']),
              })
            }
            isSaving={updatePlanning.isPending}
          />

          <EditableListSection
            title="Income sources"
            description="Salary, freelance, rental, benefits, and other cash-in sources."
            fields={[
              { key: 'label', label: 'Label', placeholder: 'Primary salary' },
              { key: 'sourceType', label: 'Type', placeholder: 'salary' },
              { key: 'payFrequency', label: 'Frequency', placeholder: 'biweekly' },
              { key: 'monthlyAmount', label: 'Monthly amount', placeholder: '8500', inputMode: 'decimal' },
            ]}
            items={sections.incomeSources}
            onChange={(items) =>
              dispatch({ type: 'UPDATE_DRAFT', section: 'incomeSources', items })
            }
            onAdd={() =>
              dispatch({
                type: 'ADD_ITEM',
                section: 'incomeSources',
                template: { label: '', sourceType: '', payFrequency: '', monthlyAmount: null },
              })
            }
            onSave={() =>
              saveSection({
                incomeSources: normalizeSection<HouseholdIncomeSourceInput>(sections.incomeSources, [
                  'monthlyAmount',
                ]),
              })
            }
            isSaving={updatePlanning.isPending}
          />

          <EditableListSection
            title="Debt obligations"
            description="Mortgage, HELOC, student loans, auto loans, and other debt service."
            fields={[
              { key: 'label', label: 'Label', placeholder: 'Primary mortgage' },
              { key: 'debtType', label: 'Type', placeholder: 'mortgage' },
              { key: 'balance', label: 'Balance', placeholder: '420000', inputMode: 'decimal' },
              { key: 'monthlyPayment', label: 'Monthly payment', placeholder: '2450', inputMode: 'decimal' },
            ]}
            items={sections.debtObligations}
            onChange={(items) =>
              dispatch({ type: 'UPDATE_DRAFT', section: 'debtObligations', items })
            }
            onAdd={() =>
              dispatch({
                type: 'ADD_ITEM',
                section: 'debtObligations',
                template: { label: '', debtType: '', balance: null, monthlyPayment: null },
              })
            }
            onSave={() =>
              saveSection({
                debtObligations: normalizeSection<HouseholdDebtObligationInput>(
                  sections.debtObligations,
                  ['balance', 'monthlyPayment'],
                ),
              })
            }
            isSaving={updatePlanning.isPending}
          />

          <EditableListSection
            title="Housing costs"
            description="Rent or owned-home carrying costs plus major housing assumptions."
            fields={[
              { key: 'label', label: 'Label', placeholder: 'Primary residence' },
              { key: 'housingType', label: 'Type', placeholder: 'own or rent' },
              { key: 'monthlyPayment', label: 'Monthly payment', placeholder: '2450', inputMode: 'decimal' },
              { key: 'mortgageBalance', label: 'Mortgage balance', placeholder: '420000', inputMode: 'decimal' },
            ]}
            items={sections.housingCosts}
            onChange={(items) =>
              dispatch({ type: 'UPDATE_DRAFT', section: 'housingCosts', items })
            }
            onAdd={() =>
              dispatch({
                type: 'ADD_ITEM',
                section: 'housingCosts',
                template: {
                  label: '',
                  housingType: '',
                  occupancyRole: 'primary',
                  monthlyPayment: null,
                  mortgageBalance: null,
                },
              })
            }
            onSave={() =>
              saveSection({
                housingCosts: normalizeSection<HouseholdHousingCostInput>(sections.housingCosts, [
                  'monthlyPayment',
                  'mortgageBalance',
                ]),
              })
            }
            isSaving={updatePlanning.isPending}
          />

          <EditableListSection
            title="Insurance policies"
            description="Coverage, premiums, and risk-transfer assumptions Jenny should respect."
            fields={[
              { key: 'label', label: 'Label', placeholder: 'Family health plan' },
              { key: 'coverageType', label: 'Coverage type', placeholder: 'health' },
              { key: 'premiumMonthly', label: 'Monthly premium', placeholder: '780', inputMode: 'decimal' },
              { key: 'coverageAmount', label: 'Coverage amount', placeholder: '500000', inputMode: 'decimal' },
            ]}
            items={sections.insurancePolicies}
            onChange={(items) =>
              dispatch({ type: 'UPDATE_DRAFT', section: 'insurancePolicies', items })
            }
            onAdd={() =>
              dispatch({
                type: 'ADD_ITEM',
                section: 'insurancePolicies',
                template: { label: '', coverageType: '', premiumMonthly: null, coverageAmount: null },
              })
            }
            onSave={() =>
              saveSection({
                insurancePolicies: normalizeSection<HouseholdInsurancePolicyInput>(
                  sections.insurancePolicies,
                  ['premiumMonthly', 'coverageAmount'],
                ),
              })
            }
            isSaving={updatePlanning.isPending}
          />

          <EditableListSection
            title="Retirement income sources"
            description="Social Security, pensions, annuities, and bridge income."
            fields={[
              { key: 'label', label: 'Label', placeholder: 'Social Security - Jamie' },
              { key: 'sourceType', label: 'Type', placeholder: 'social_security' },
              { key: 'startAge', label: 'Start age', placeholder: '67', inputMode: 'numeric' },
              { key: 'monthlyAmount', label: 'Monthly amount', placeholder: '2800', inputMode: 'decimal' },
            ]}
            items={sections.retirementIncomeSources}
            onChange={(items) =>
              dispatch({ type: 'UPDATE_DRAFT', section: 'retirementIncomeSources', items })
            }
            onAdd={() =>
              dispatch({
                type: 'ADD_ITEM',
                section: 'retirementIncomeSources',
                template: { label: '', sourceType: '', startAge: null, monthlyAmount: null },
              })
            }
            onSave={() =>
              saveSection({
                retirementIncomeSources:
                  normalizeSection<HouseholdRetirementIncomeSourceInput>(
                    sections.retirementIncomeSources,
                    ['startAge', 'monthlyAmount'],
                  ),
              })
            }
            isSaving={updatePlanning.isPending}
          />

          <EditableListSection
            title="Major expenses and goal buckets"
            description="Large one-time costs and sinking-fund style future goals."
            fields={[
              { key: 'label', label: 'Label', placeholder: 'Roof replacement' },
              { key: 'expenseKind', label: 'Kind', placeholder: 'major_expense or goal_bucket' },
              { key: 'targetAmount', label: 'Target amount', placeholder: '18000', inputMode: 'decimal' },
              { key: 'targetDate', label: 'Target date', type: 'date' },
            ]}
            items={sections.plannedExpenses}
            onChange={(items) =>
              dispatch({ type: 'UPDATE_DRAFT', section: 'plannedExpenses', items })
            }
            onAdd={() =>
              dispatch({
                type: 'ADD_ITEM',
                section: 'plannedExpenses',
                template: {
                  label: '',
                  expenseKind: '',
                  category: 'general',
                  targetAmount: null,
                  targetDate: null,
                },
              })
            }
            onSave={() =>
              saveSection({
                plannedExpenses: normalizeSection<HouseholdPlannedExpenseInput>(
                  sections.plannedExpenses,
                  ['targetAmount'],
                ),
              })
            }
            isSaving={updatePlanning.isPending}
          />

          <HouseholdPlanningDocumentsCard
            requirements={planning.documentRequirements}
            statusBadge={statusBadge}
          />
        </div>
      </SectionCard>
    </div>
  )
}
