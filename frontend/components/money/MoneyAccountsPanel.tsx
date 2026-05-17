'use client'

import { PlusCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { InfoBadge } from '@/components/shared/InfoBadge'
import { Accordion } from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import type {
  HouseholdAccountControl,
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

function accountControlBadgeVariant(
  status: string | undefined,
  blockingIssueCount: number | undefined,
) {
  if (status === 'blocked' || (blockingIssueCount ?? 0) > 0) {
    return 'error' as const
  }
  if (status === 'review') {
    return 'warning' as const
  }
  return 'success' as const
}

function accountControlLabel(
  status: string | undefined,
  blockingIssueCount: number | undefined,
) {
  if (status === 'blocked' || (blockingIssueCount ?? 0) > 0) {
    return 'Blocked'
  }
  if (status === 'review') {
    return 'Review'
  }
  return 'Clear'
}

function issueToneClass(severity: string) {
  switch (severity) {
    case 'high':
      return 'border-loss/25 bg-loss/8 text-loss'
    case 'medium':
      return 'border-warning/25 bg-warning/8 text-warning'
    default:
      return 'border-border/40 bg-surface/70 text-text-muted'
  }
}

export function MoneyAccountsPanel({
  accounts,
  documents,
  accountControl,
  discoveredAccounts = [],
  focus = null,
  selectedAccountId = null,
  intent = null,
}: {
  accounts: HouseholdAccountSummary[]
  documents: HouseholdDocument[]
  accountControl?: HouseholdAccountControl
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
  const accountControlNeedsReview = Boolean(
    accountControl && accountControl.status !== 'clear',
  )
  const accountControlIssues = accountControl?.issues.slice(0, 3) ?? []

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

      {accountControlNeedsReview ? (
        <div
          id="account-coverage"
          className="rounded-3xl border border-warning/25 bg-warning/5 p-5"
        >
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-sm font-semibold text-text">
                Account Controls
              </p>
              <p className="mt-1 text-sm leading-relaxed text-text-muted">
                {accountControl?.summary}
              </p>
            </div>
            <InfoBadge
              label={accountControlLabel(
                accountControl?.status,
                accountControl?.blockingIssueCount,
              )}
              detail={`${accountControl?.issueCount ?? 0} issue${accountControl?.issueCount === 1 ? '' : 's'}`}
              variant={accountControlBadgeVariant(
                accountControl?.status,
                accountControl?.blockingIssueCount,
              )}
              interactive={false}
            />
          </div>
          {accountControlIssues.length > 0 ? (
            <div className="mt-4 divide-y divide-warning/20 rounded-2xl border border-warning/25 bg-background/35">
              {accountControlIssues.map((issue) => (
                <div
                  key={issue.id}
                  className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-start"
                >
                  <div>
                    <p className="text-sm font-medium text-text">
                      {issue.title}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-text-muted">
                      {issue.detail}
                    </p>
                  </div>
                  <span
                    className={`w-fit rounded-full border px-2.5 py-1 text-xs capitalize ${issueToneClass(
                      issue.severity,
                    )}`}
                  >
                    {issue.severity}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

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
