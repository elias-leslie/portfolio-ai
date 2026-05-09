'use client'

import { PlusCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Accordion } from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import type {
  HouseholdAccountSummary,
  HouseholdDiscoveredAccount,
  HouseholdDocument,
  HouseholdTrackedAccountInput,
} from '@/lib/api/household'
import { useDeleteHouseholdTrackedAccount } from '@/lib/hooks/useHousehold'
import { AccountAccordionItem } from './AccountAccordionItem'
import { DeleteAccountDialog } from './DeleteAccountDialog'
import { DiscoveredAccountsSection } from './DiscoveredAccountsSection'
import { TrackedAccountDialog } from './TrackedAccountDialog'

type MoneyAccountsFocus = 'coverage' | 'discovered' | null
type MoneyAccountsIntent = 'evidence' | 'review' | null

export function MoneyAccountsPanel({
  accounts,
  documents,
  discoveredAccounts = [],
  focus = null,
  selectedAccountId = null,
  intent = null,
}: {
  accounts: HouseholdAccountSummary[]
  documents: HouseholdDocument[]
  discoveredAccounts?: HouseholdDiscoveredAccount[]
  focus?: MoneyAccountsFocus
  selectedAccountId?: string | null
  intent?: MoneyAccountsIntent
}) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingAccount, setEditingAccount] =
    useState<HouseholdAccountSummary | null>(null)
  const [draftSeed, setDraftSeed] =
    useState<HouseholdTrackedAccountInput | null>(null)
  const [deletingAccount, setDeletingAccount] =
    useState<HouseholdAccountSummary | null>(null)

  const focusedAccountId =
    selectedAccountId ??
    (focus === 'coverage'
      ? accounts.find(
          (a) => a.gapFlags.length > 0 || a.freshnessStatus !== 'fresh',
        )?.id
      : undefined)

  const [openAccountId, setOpenAccountId] = useState<string | undefined>(
    focusedAccountId,
  )

  const deleteAccount = useDeleteHouseholdTrackedAccount()
  const documentsById = Object.fromEntries(documents.map((d) => [d.id, d]))

  useEffect(() => {
    if (focusedAccountId) setOpenAccountId(focusedAccountId)
  }, [focusedAccountId])

  useEffect(() => {
    if (!selectedAccountId || openAccountId !== selectedAccountId) return
    const targetId =
      intent === 'evidence'
        ? `account-evidence-upload-${selectedAccountId}`
        : `account-${selectedAccountId}`
    const scrollTarget = document.getElementById(targetId)
    if (!scrollTarget) return
    requestAnimationFrame(() => {
      scrollTarget.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
    })
  }, [intent, openAccountId, selectedAccountId])

  const handleDelete = async (account: HouseholdAccountSummary) => {
    if (!account.trackedAccountId) return
    await deleteAccount.mutateAsync(account.trackedAccountId)
    setDeletingAccount(null)
  }

  const openAddDialog = () => {
    setEditingAccount(null)
    setDraftSeed(null)
    setDialogOpen(true)
  }

  const openEditDialog = (account: HouseholdAccountSummary) => {
    setEditingAccount(account)
    setDraftSeed(null)
    setDialogOpen(true)
  }

  const openSeedDialog = (seed: HouseholdTrackedAccountInput) => {
    setEditingAccount(null)
    setDraftSeed(seed)
    setDialogOpen(true)
  }

  return (
    <div className="space-y-4">
      <DiscoveredAccountsSection
        accounts={discoveredAccounts}
        focus={focus}
        onSeed={openSeedDialog}
      />

      <div className="flex flex-col gap-3 rounded-3xl border border-border/40 bg-surface-muted/15 p-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold text-text">Accounts</p>
          <p className="mt-1 text-sm text-text-muted">
            Expand a row for uploads, documents, and account details.
          </p>
        </div>
        <Button type="button" onClick={openAddDialog}>
          <PlusCircle className="mr-2 h-4 w-4" />
          Add account
        </Button>
      </div>

      {accounts.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
          No accounts yet. Add one manually or upload evidence and let Jenny
          create the first account candidates for you.
        </div>
      ) : (
        <div className="rounded-3xl border border-border/40 bg-surface/55">
          <Accordion
            type="single"
            collapsible
            className="w-full"
            value={openAccountId}
            onValueChange={setOpenAccountId}
          >
            {accounts.map((account) => (
              <AccountAccordionItem
                key={account.id}
                account={account}
                documentsById={documentsById}
                focusedAccountId={focusedAccountId}
                selectedAccountId={selectedAccountId}
                intent={intent}
                isPendingDelete={deleteAccount.isPending}
                onEdit={openEditDialog}
                onDelete={setDeletingAccount}
              />
            ))}
          </Accordion>
        </div>
      )}

      <TrackedAccountDialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open)
          if (!open) {
            setEditingAccount(null)
            setDraftSeed(null)
          }
        }}
        account={editingAccount}
        seed={draftSeed}
      />

      <DeleteAccountDialog
        account={deletingAccount}
        isPending={deleteAccount.isPending}
        onCancel={() => setDeletingAccount(null)}
        onConfirm={(account) => void handleDelete(account)}
      />
    </div>
  )
}
