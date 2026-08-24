'use client'

import { useEffect, useState } from 'react'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { useHouseholdDashboard } from '@/lib/hooks/useHousehold'
import { AllocationCard } from './AllocationCard'
import { formatAssetGroup, normalizeTrustStatus } from './overview-helpers'

/**
 * The account allocation donut, self-contained, for the Investing workspace.
 *
 * It used to sit on the Money dashboard beside four decision cards, deriving
 * its state from the whole Decision Board hook. Allocation is a question about
 * where the assets are, which is what Investing is for; Money's job is what
 * came in and what went out. Pulling the derivation in here is what let the
 * donut move without dragging the rest of that hook with it.
 */
export function AccountAllocationSection({
  dashboard: dashboardProp,
}: {
  dashboard?: HouseholdFinanceDashboard
}) {
  const { data: dashboardQuery } = useHouseholdDashboard()
  const dashboard = dashboardProp ?? dashboardQuery

  // Backend owns the allocation math (credit/debt excluded, sorted desc); the
  // map here is purely a label transform.
  const allocationData = (dashboard?.overview.assetAllocation ?? []).map(
    (slice) => ({
      assetGroup: slice.assetGroup,
      label: formatAssetGroup(slice.assetGroup),
      value: slice.totalValue,
    }),
  )
  const [selectedAssetGroup, setSelectedAssetGroup] = useState<string | null>(
    allocationData[0]?.assetGroup ?? null,
  )

  useEffect(() => {
    if (
      !allocationData.some((item) => item.assetGroup === selectedAssetGroup)
    ) {
      setSelectedAssetGroup(allocationData[0]?.assetGroup ?? null)
    }
  }, [allocationData, selectedAssetGroup])

  if (!dashboard) {
    return null
  }

  const selectedAccounts = dashboard.accounts.filter(
    (account) => account.assetGroup === selectedAssetGroup,
  )

  return (
    <AllocationCard
      dashboard={dashboard}
      allocationData={allocationData}
      selectedAssetGroup={selectedAssetGroup}
      setSelectedAssetGroup={setSelectedAssetGroup}
      selectedAccounts={selectedAccounts}
      netWorthTrustStatus={normalizeTrustStatus(
        dashboard.overview.netWorthStatus,
      )}
    />
  )
}
