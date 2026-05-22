'use client'

import { HouseholdPlanningPanels } from '@/components/money/HouseholdPlanningPanels'
import { MoneyAssumptionsDrawer } from '@/components/money/MoneyAssumptionsDrawer'
import { MoneyDataServicesDrawer } from '@/components/money/MoneyDataServicesDrawer'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type {
  HouseholdConfirmedFact,
  HouseholdFinanceDashboard,
} from '@/lib/api/household'
import type { MoneyFocus, MoneyUtility } from './money-route-state'
import { isPlanningFocus } from './money-route-state'

type Props = {
  openUtility: MoneyUtility | null
  focusedReview: MoneyFocus | null
  dashboard: HouseholdFinanceDashboard
  facts: HouseholdConfirmedFact[]
  onUtilityChange: (next: MoneyUtility | null) => void
}

export function MoneyUtilityDrawers({
  openUtility,
  focusedReview,
  dashboard,
  facts,
  onUtilityChange,
}: Props) {
  return (
    <>
      <Dialog
        open={openUtility === 'planning'}
        onOpenChange={(open) => onUtilityChange(open ? 'planning' : null)}
      >
        <DialogContent className="left-auto right-0 top-0 h-dvh max-w-[min(980px,100vw)] translate-x-0 translate-y-0 rounded-none border-l border-border/45 p-0 sm:max-w-[min(980px,100vw)]">
          <div className="max-h-dvh overflow-y-auto p-6">
            <DialogHeader>
              <DialogTitle>Assumptions</DialogTitle>
              <DialogDescription>
                Confirm what Jenny found, override it when needed, and keep the
                manual finance inputs in one minimal workspace.
              </DialogDescription>
            </DialogHeader>
            <div className="mt-4">
              <MoneyAssumptionsDrawer
                profile={dashboard.profile}
                resolvedValues={dashboard.resolvedValues}
                facts={facts}
                planningContent={
                  isPlanningFocus(focusedReview) &&
                  focusedReview !== 'income' &&
                  focusedReview !== 'retirement' ? (
                    <HouseholdPlanningPanels
                      dashboard={dashboard}
                      focusedSection={focusedReview}
                    />
                  ) : undefined
                }
              />
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={openUtility === 'data-services'}
        modal={false}
        onOpenChange={(open) => onUtilityChange(open ? 'data-services' : null)}
      >
        <DialogContent className="left-auto right-0 top-0 h-dvh max-w-[min(1040px,100vw)] translate-x-0 translate-y-0 rounded-none border-l border-border/45 p-0 sm:max-w-[min(1040px,100vw)]">
          <div className="max-h-dvh overflow-y-auto p-6">
            <DialogHeader>
              <DialogTitle>Data Services</DialogTitle>
              <DialogDescription>
                External financial data connections for household accounts,
                balances, positions, activities, and transactions.
              </DialogDescription>
            </DialogHeader>
            <div className="mt-4">
              <MoneyDataServicesDrawer />
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
