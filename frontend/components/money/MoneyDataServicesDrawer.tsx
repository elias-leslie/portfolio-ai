'use client'

import type { ComponentType } from 'react'
import { PlaidLinkPanel } from '@/components/money/PlaidLinkPanel'
import { SnapTradePanel } from '@/components/money/SnapTradePanel'

const DATA_SERVICE_PANELS = [
  {
    id: 'plaid',
    Panel: PlaidLinkPanel,
  },
  {
    id: 'snaptrade',
    Panel: SnapTradePanel,
  },
] satisfies Array<{ id: string; Panel: ComponentType }>

export function MoneyDataServicesDrawer() {
  return (
    <div className="space-y-4">
      {DATA_SERVICE_PANELS.map(({ id, Panel }) => (
        <Panel key={id} />
      ))}
    </div>
  )
}
