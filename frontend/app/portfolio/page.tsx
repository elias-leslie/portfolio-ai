'use client'

import { useState } from 'react'
import { AccountsWithPositionsContent } from '@/components/portfolio/AccountsWithPositions'
import { AddAccountDialog } from '@/components/portfolio/AddAccountDialog'
import { AddPositionDialog } from '@/components/portfolio/AddPositionDialog'
import { PortfolioOverview } from '@/components/portfolio/PortfolioOverview'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { useAccounts } from '@/lib/hooks/usePortfolio'

export default function PortfolioPage() {
  const {
    data: accounts,
    isLoading: accountsLoading,
    isFetching: accountsFetching,
    error: accountsError,
    refetch: refetchAccounts,
  } = useAccounts()

  const [accountOpen, setAccountOpen] = useState(false)
  const [positionOpen, setPositionOpen] = useState(false)
  const [positionDialogKey, setPositionDialogKey] = useState(0)
  const [defaultAccountId, setDefaultAccountId] = useState('')

  const hasAccounts = (accounts?.length ?? 0) > 0

  const openPositionDialog = (nextAccountId?: string) => {
    const id = nextAccountId ?? (accounts?.length === 1 ? accounts[0].id : '')
    setDefaultAccountId(id)
    setPositionDialogKey((k) => k + 1)
    setPositionOpen(true)
  }

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        title="Portfolio Coach"
        description="Review your holdings, spot concentration risk, and keep position sizes honest."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setAccountOpen(true)}>
              Add Account
            </Button>
            <Button
              onClick={() => openPositionDialog()}
              disabled={!hasAccounts || accountsLoading}
            >
              Add Position
            </Button>
          </div>
        }
      />

      {!accountsLoading && !hasAccounts ? (
        <div className="rounded-2xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          Create an account before adding your first position so portfolio
          coaching has account context.
        </div>
      ) : null}

      <PortfolioOverview />

      <AccountsWithPositionsContent
        accounts={accounts}
        accountsLoading={accountsLoading}
        accountsFetching={accountsFetching}
        accountsError={accountsError}
        onRetryAccounts={() => {
          void refetchAccounts()
        }}
        onAddAccount={() => setAccountOpen(true)}
        onAddPosition={openPositionDialog}
      />

      <AddAccountDialog open={accountOpen} onOpenChange={setAccountOpen} />

      <AddPositionDialog
        key={positionDialogKey}
        open={positionOpen}
        onOpenChange={setPositionOpen}
        defaultAccountId={defaultAccountId}
      />
    </PageContainer>
  )
}
