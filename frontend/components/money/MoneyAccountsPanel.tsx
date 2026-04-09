'use client'

import { useEffect, useState } from 'react'
import { Pencil, PlusCircle, Trash2 } from 'lucide-react'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type {
  HouseholdAccountSummary,
  HouseholdDocument,
  HouseholdTrackedAccountInput,
} from '@/lib/api/household'
import {
  useCreateHouseholdTrackedAccount,
  useDeleteHouseholdTrackedAccount,
  useUpdateHouseholdTrackedAccount,
} from '@/lib/hooks/useHousehold'
import { formatCurrencyWhole } from '@/lib/formatters'
import { formatRelativeTime } from '@/lib/utils'
import { EvidenceUploadComposer } from './EvidenceUploadComposer'

const freshnessTone = {
  fresh: 'border-gain/25 bg-gain/5 text-gain',
  aging: 'border-warning/25 bg-warning/5 text-warning',
  stale: 'border-loss/25 bg-loss/5 text-loss',
  needs_evidence: 'border-primary/25 bg-primary/5 text-primary',
}

const ASSET_GROUP_OPTIONS = [
  { value: 'cash', label: 'Cash' },
  { value: 'credit', label: 'Credit' },
  { value: 'debt', label: 'Debt' },
  { value: 'retirement', label: 'Retirement' },
  { value: 'taxable', label: 'Taxable' },
  { value: 'education', label: 'Education' },
  { value: 'other', label: 'Other' },
] as const

const ACCOUNT_TYPE_OPTIONS: Record<string, { value: string; label: string }[]> = {
  cash: [
    { value: 'checking', label: 'Checking' },
    { value: 'savings', label: 'Savings' },
    { value: 'cash_management', label: 'Cash management' },
  ],
  credit: [{ value: 'credit_card', label: 'Credit card' }],
  debt: [
    { value: 'mortgage', label: 'Mortgage' },
    { value: 'loan', label: 'Loan' },
    { value: 'line_of_credit', label: 'Line of credit' },
  ],
  retirement: [
    { value: 'ira', label: 'IRA' },
    { value: 'roth', label: 'Roth IRA' },
    { value: '401k', label: '401(k)' },
    { value: 'hsa', label: 'HSA' },
  ],
  taxable: [{ value: 'brokerage', label: 'Brokerage' }],
  education: [{ value: '529', label: '529' }],
  other: [{ value: 'other', label: 'Other' }],
}

const SOURCE_TYPE_BY_ASSET_GROUP: Record<string, string> = {
  cash: 'bank',
  credit: 'credit_card',
  debt: 'debt',
  retirement: 'retirement',
  taxable: 'brokerage',
  education: 'education',
  other: 'other',
}

interface TrackedAccountDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  account?: HouseholdAccountSummary | null
}

function defaultAccountType(assetGroup: string) {
  return ACCOUNT_TYPE_OPTIONS[assetGroup]?.[0]?.value ?? 'other'
}

function buildInitialState(
  account?: HouseholdAccountSummary | null,
): HouseholdTrackedAccountInput {
  const assetGroup = account?.assetGroup ?? 'cash'
  return {
    label: account?.label ?? '',
    assetGroup,
    accountType: account?.accountType ?? defaultAccountType(assetGroup),
    sourceType: account?.sourceType ?? SOURCE_TYPE_BY_ASSET_GROUP[assetGroup] ?? 'other',
    institutionName: account?.institutionName ?? '',
    ownerName: account?.ownerName ?? '',
    accountMask: account?.accountMask ?? '',
    notes: account?.notes ?? '',
  }
}

function TrackedAccountDialog({
  open,
  onOpenChange,
  account = null,
}: TrackedAccountDialogProps) {
  const createAccount = useCreateHouseholdTrackedAccount()
  const updateAccount = useUpdateHouseholdTrackedAccount()
  const [form, setForm] = useState<HouseholdTrackedAccountInput>(
    buildInitialState(account),
  )

  useEffect(() => {
    if (open) {
      setForm(buildInitialState(account))
    }
  }, [account, open])

  const accountTypeOptions = ACCOUNT_TYPE_OPTIONS[form.assetGroup] ?? ACCOUNT_TYPE_OPTIONS.other
  const canSubmit = form.label.trim().length > 0
  const isEditing = Boolean(account?.trackedAccountId)

  const setAssetGroup = (assetGroup: string) => {
    setForm((current) => ({
      ...current,
      assetGroup,
      accountType: defaultAccountType(assetGroup),
      sourceType: SOURCE_TYPE_BY_ASSET_GROUP[assetGroup] ?? 'other',
    }))
  }

  const handleSubmit = async () => {
    if (!canSubmit) return
    if (isEditing && account?.trackedAccountId) {
      await updateAccount.mutateAsync({
        accountId: account.trackedAccountId,
        payload: form,
      })
    } else {
      await createAccount.mutateAsync(form)
    }
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit tracked account' : 'Add tracked account'}</DialogTitle>
          <DialogDescription>
            Create a real account row first, then let Jenny attach evidence to it over time.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label htmlFor="money-account-label">Account label</Label>
            <Input
              id="money-account-label"
              value={form.label}
              onChange={(event) =>
                setForm((current) => ({ ...current, label: event.target.value }))
              }
              placeholder="Joint Checking"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="money-account-group">Asset group</Label>
              <Select value={form.assetGroup} onValueChange={setAssetGroup}>
                <SelectTrigger id="money-account-group">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ASSET_GROUP_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="money-account-type">Account type</Label>
              <Select
                value={form.accountType}
                onValueChange={(accountType) =>
                  setForm((current) => ({ ...current, accountType }))
                }
              >
                <SelectTrigger id="money-account-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {accountTypeOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="money-account-institution">Institution</Label>
              <Input
                id="money-account-institution"
                value={form.institutionName ?? ''}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    institutionName: event.target.value,
                  }))
                }
                placeholder="Wells Fargo"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="money-account-mask">Account mask</Label>
              <Input
                id="money-account-mask"
                value={form.accountMask ?? ''}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    accountMask: event.target.value,
                  }))
                }
                placeholder="4421"
              />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="money-account-notes">Notes</Label>
            <Input
              id="money-account-notes"
              value={form.notes ?? ''}
              onChange={(event) =>
                setForm((current) => ({ ...current, notes: event.target.value }))
              }
              placeholder="Primary bills account"
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={
              !canSubmit || createAccount.isPending || updateAccount.isPending
            }
            aria-busy={createAccount.isPending || updateAccount.isPending}
          >
            {createAccount.isPending || updateAccount.isPending
              ? 'Saving...'
              : isEditing
                ? 'Save account'
                : 'Create account'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function accountMetaLine(account: HouseholdAccountSummary) {
  const parts = [account.assetGroup, account.accountType]
  if (account.institutionName) {
    parts.push(account.institutionName)
  }
  return parts.join(' · ')
}

function accountSubline(account: HouseholdAccountSummary) {
  if (account.linkedPortfolioAccountName) {
    return `Linked to ${account.linkedPortfolioAccountName}`
  }
  if (account.lastEvidenceAt) {
    return `Last evidence ${formatRelativeTime(account.lastEvidenceAt)}`
  }
  return 'No evidence linked yet'
}

export function MoneyAccountsPanel({
  accounts,
  documents,
}: {
  accounts: HouseholdAccountSummary[]
  documents: HouseholdDocument[]
}) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingAccount, setEditingAccount] = useState<HouseholdAccountSummary | null>(null)
  const [deletingAccount, setDeletingAccount] =
    useState<HouseholdAccountSummary | null>(null)
  const deleteAccount = useDeleteHouseholdTrackedAccount()
  const documentsById = Object.fromEntries(
    documents.map((document) => [document.id, document]),
  )

  const handleDelete = async (account: HouseholdAccountSummary) => {
    if (!account.trackedAccountId) return
    await deleteAccount.mutateAsync(account.trackedAccountId)
    setDeletingAccount(null)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-3xl border border-border/40 bg-surface-muted/15 p-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold text-text">Tracked accounts</p>
          <p className="mt-1 text-sm text-text-muted">
            Expand a row for the details, latest evidence, gaps, and direct
            account-scoped uploads. If you do not know the account yet, use the
            generic add-anything flow instead.
          </p>
        </div>
        <Button
          type="button"
          onClick={() => {
            setEditingAccount(null)
            setDialogOpen(true)
          }}
        >
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
          <Accordion type="single" collapsible className="w-full">
            {accounts.map((account) => {
              const topGap = account.gapFlags[0] ?? null
              return (
                <AccordionItem
                  key={account.id}
                  value={account.id}
                  id={`account-${account.id}`}
                  className="px-5"
                >
                  <AccordionTrigger className="py-5 hover:text-text">
                    <div className="grid flex-1 gap-3 text-left md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_auto] md:items-center">
                      <div className="min-w-0">
                        <p className="truncate text-base font-semibold text-text">
                          {account.label}
                        </p>
                        <p className="mt-1 truncate text-sm text-text-muted">
                          {accountMetaLine(account)}
                        </p>
                        <p className="mt-1 text-xs text-text-muted">
                          {accountSubline(account)}
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <span
                          className={`rounded-full border px-2.5 py-1 text-xs ${
                            freshnessTone[
                              account.freshnessStatus as keyof typeof freshnessTone
                            ] ?? freshnessTone.needs_evidence
                          }`}
                        >
                          {account.freshnessLabel}
                        </span>
                        <span className="rounded-full border border-border/40 bg-surface/70 px-2.5 py-1 text-xs text-text-muted">
                          {account.evidenceCount} source
                          {account.evidenceCount === 1 ? '' : 's'}
                        </span>
                        {topGap ? (
                          <span className="rounded-full border border-border/40 bg-surface/70 px-2.5 py-1 text-xs text-text-muted">
                            {topGap.title}
                          </span>
                        ) : null}
                      </div>

                      <div className="text-left md:text-right">
                        <p className="text-lg font-semibold tabular-nums text-text">
                          {account.currentValue != null
                            ? formatCurrencyWhole(account.currentValue)
                            : '—'}
                        </p>
                        <p className="mt-1 text-xs text-text-muted">
                          {account.matchConfidence != null
                            ? `${Math.round(account.matchConfidence * 100)}% confidence`
                            : 'Awaiting evidence'}
                        </p>
                      </div>
                    </div>
                  </AccordionTrigger>

                  <AccordionContent className="pb-5">
                    <div className="grid gap-4 xl:grid-cols-[0.92fr_1.08fr]">
                      <div className="space-y-4">
                        <div className="grid gap-3 sm:grid-cols-3">
                          <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                              Freshness
                            </p>
                            <p className="mt-2 text-sm font-semibold text-text">
                              {account.freshnessLabel}
                            </p>
                          </div>
                          <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                              Status
                            </p>
                            <p className="mt-2 text-sm font-semibold text-text">
                              {account.accountOrigin === 'tracked'
                                ? 'Tracked account'
                                : account.accountOrigin === 'portfolio'
                                  ? 'Portfolio account'
                                  : account.matchStatus === 'candidate'
                                    ? 'Candidate account'
                                    : 'Evidence-backed'}
                            </p>
                          </div>
                          <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                              Documents
                            </p>
                            <p className="mt-2 text-sm font-semibold text-text">
                              {account.evidenceCount}
                            </p>
                          </div>
                        </div>

                        {account.gapFlags.length > 0 ? (
                          <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                              Gaps Jenny sees
                            </p>
                            <div className="mt-3 space-y-3">
                              {account.gapFlags.map((gap) => (
                                <div
                                  key={`${account.id}-${gap.code}`}
                                  className="rounded-2xl border border-border/30 bg-surface/70 p-3"
                                >
                                  <div className="flex items-center justify-between gap-3">
                                    <p className="text-sm font-semibold text-text">
                                      {gap.title}
                                    </p>
                                    <span className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
                                      {gap.severity}
                                    </span>
                                  </div>
                                  <p className="mt-2 text-sm text-text-muted">
                                    {gap.detail}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}

                        <EvidenceUploadComposer
                          compact
                          title="Add evidence to this account"
                          description="Use this when you already know the account. Jenny still verifies the contents before applying any update."
                          accountLabel={account.label}
                        />
                      </div>

                      <div className="space-y-4">
                        <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                              Supporting documents
                            </p>
                            {account.trackedAccountId ? (
                              <div className="flex gap-2">
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    setEditingAccount(account)
                                    setDialogOpen(true)
                                  }}
                                >
                                  <Pencil className="mr-2 h-4 w-4" />
                                  Edit
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setDeletingAccount(account)}
                                  disabled={deleteAccount.isPending}
                                  aria-busy={deleteAccount.isPending}
                                >
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  Delete
                                </Button>
                              </div>
                            ) : null}
                          </div>

                          {account.documentIds.length === 0 ? (
                            <p className="mt-3 text-sm text-text-muted">
                              No supporting documents are attached yet.
                            </p>
                          ) : (
                            <div className="mt-3 space-y-2">
                              {account.documentIds.map((documentId) => {
                                const document = documentsById[documentId]
                                return (
                                  <div
                                    key={documentId}
                                    className="flex items-center justify-between gap-3 rounded-2xl border border-border/30 bg-surface/70 px-3 py-3"
                                  >
                                    <div className="min-w-0">
                                      <p className="truncate text-sm font-medium text-text">
                                        {document?.filename ?? documentId}
                                      </p>
                                      <p className="mt-1 text-xs text-text-muted">
                                        {document?.sourceType ?? 'unknown'} ·{' '}
                                        {document?.status ?? 'stored review'}
                                      </p>
                                    </div>
                                    <span className="shrink-0 text-xs text-text-muted">
                                      {document?.uploadedAt
                                        ? formatRelativeTime(document.uploadedAt)
                                        : 'Stored review'}
                                    </span>
                                  </div>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )
            })}
          </Accordion>
        </div>
      )}

      <TrackedAccountDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        account={editingAccount}
      />

      <Dialog
        open={Boolean(deletingAccount)}
        onOpenChange={(open) => {
          if (!open && !deleteAccount.isPending) {
            setDeletingAccount(null)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete tracked account</DialogTitle>
            <DialogDescription>
              Remove the tracked row for{' '}
              <span className="font-medium text-text">
                {deletingAccount?.label ?? 'this account'}
              </span>
              . Existing uploaded evidence will remain in intake history.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDeletingAccount(null)}
              disabled={deleteAccount.isPending}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => {
                if (deletingAccount) {
                  void handleDelete(deletingAccount)
                }
              }}
              disabled={!deletingAccount || deleteAccount.isPending}
              aria-busy={deleteAccount.isPending}
            >
              {deleteAccount.isPending ? 'Deleting...' : 'Delete account'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
