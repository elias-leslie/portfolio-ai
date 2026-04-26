'use client'

import { Pencil, PlusCircle, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { InfoBadge } from '@/components/shared/InfoBadge'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
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
  HouseholdDiscoveredAccount,
  HouseholdDocument,
  HouseholdTrackedAccountInput,
} from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import {
  useCreateHouseholdTrackedAccount,
  useDeleteHouseholdTrackedAccount,
  useUpdateHouseholdTrackedAccount,
} from '@/lib/hooks/useHousehold'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import { EvidenceUploadComposer } from './EvidenceUploadComposer'

type MoneyAccountsFocus = 'coverage' | 'discovered' | null
type MoneyAccountsIntent = 'evidence' | 'review' | null

const freshnessTone = {
  fresh: 'border-gain/25 bg-gain/5 text-gain',
  aging: 'border-warning/25 bg-warning/5 text-warning',
  stale: 'border-loss/25 bg-loss/5 text-loss',
  needs_evidence: 'border-primary/25 bg-primary/5 text-primary',
  not_applicable: 'border-border/40 bg-surface/70 text-text-muted',
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

const ACCOUNT_TYPE_OPTIONS: Record<string, { value: string; label: string }[]> =
  {
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
  seed?: HouseholdTrackedAccountInput | null
}

function defaultAccountType(assetGroup: string) {
  return ACCOUNT_TYPE_OPTIONS[assetGroup]?.[0]?.value ?? 'other'
}

function identityManagedByCanonicalAccount(
  account?: HouseholdAccountSummary | null,
): boolean {
  if (!account) {
    return false
  }
  return Boolean(
    account.householdAccountId ||
      account.accountOrigin === 'evidence' ||
      account.accountOrigin === 'portfolio' ||
      account.matchStatus === 'linked',
  )
}

function buildInitialState(
  account?: HouseholdAccountSummary | null,
  seed?: HouseholdTrackedAccountInput | null,
): HouseholdTrackedAccountInput {
  const assetGroup = account?.assetGroup ?? seed?.assetGroup ?? 'cash'
  return {
    label: account?.label ?? seed?.label ?? '',
    assetGroup,
    accountType:
      account?.accountType ??
      seed?.accountType ??
      defaultAccountType(assetGroup),
    sourceType:
      account?.sourceType ??
      seed?.sourceType ??
      SOURCE_TYPE_BY_ASSET_GROUP[assetGroup] ??
      'other',
    matchKey:
      account?.matchKey ??
      seed?.matchKey ??
      (account && account.accountOrigin !== 'tracked' ? account.id : '') ??
      '',
    institutionName: account?.institutionName ?? seed?.institutionName ?? '',
    ownerName: account?.ownerName ?? seed?.ownerName ?? '',
    accountMask: account?.accountMask ?? seed?.accountMask ?? '',
    notes: account?.notes ?? seed?.notes ?? '',
  }
}

function TrackedAccountDialog({
  open,
  onOpenChange,
  account = null,
  seed = null,
}: TrackedAccountDialogProps) {
  const createAccount = useCreateHouseholdTrackedAccount()
  const updateAccount = useUpdateHouseholdTrackedAccount()
  const [form, setForm] = useState<HouseholdTrackedAccountInput>(
    buildInitialState(account, seed),
  )

  useEffect(() => {
    if (open) {
      setForm(buildInitialState(account, seed))
    }
  }, [account, open, seed])

  const accountTypeOptions =
    ACCOUNT_TYPE_OPTIONS[form.assetGroup] ?? ACCOUNT_TYPE_OPTIONS.other
  const canSubmit = form.label.trim().length > 0
  const isEditing = Boolean(account?.trackedAccountId)
  const isPrefilled = Boolean(seed) && !isEditing
  const identityLocked = Boolean(
    isEditing && identityManagedByCanonicalAccount(account),
  )
  const ownerLocked = false
  const dialogTitle = identityLocked
    ? 'Edit linked account'
    : isEditing
      ? 'Edit tracked account'
      : isPrefilled
        ? 'Track account'
        : 'Add tracked account'
  const dialogDescription = isPrefilled
    ? 'Jenny found this account from evidence. Confirm the details once, then keep attaching evidence to this row over time.'
    : identityLocked
      ? 'Update label, display owner, or notes here. Identity fields stay tied to linked evidence so one account cannot silently turn into another.'
      : 'Create a real account row first, then let Jenny attach evidence to it over time.'
  const submitLabel = identityLocked
    ? 'Save account details'
    : isEditing
      ? 'Save account'
      : isPrefilled
        ? 'Save account details'
        : 'Create account'

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
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription>{dialogDescription}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label htmlFor="money-account-label">Account label</Label>
            <Input
              id="money-account-label"
              value={form.label}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  label: event.target.value,
                }))
              }
              placeholder="Joint Checking"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="money-account-group">Asset group</Label>
              <Select
                value={form.assetGroup}
                onValueChange={setAssetGroup}
                disabled={identityLocked}
              >
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
                disabled={identityLocked}
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
                disabled={identityLocked}
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
                disabled={identityLocked}
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
            <Label htmlFor="money-account-owner">Owner</Label>
            <Input
              id="money-account-owner"
              value={form.ownerName ?? ''}
              disabled={ownerLocked}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  ownerName: event.target.value,
                }))
              }
              placeholder="Elias B. Leslie"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="money-account-notes">Notes</Label>
            <Input
              id="money-account-notes"
              value={form.notes ?? ''}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  notes: event.target.value,
                }))
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
              : submitLabel}
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
  if (account.ownerName) {
    parts.push(account.ownerName)
  }
  return parts.join(' · ')
}

function accountSubline(account: HouseholdAccountSummary) {
  const parts: string[] = []
  if (account.linkedPortfolioAccountName) {
    parts.push(`Linked to ${account.linkedPortfolioAccountName}`)
  }
  if (parts.length === 0 && account.evidenceCount > 0) {
    parts.push(
      account.evidenceCount === 1
        ? '1 supporting document'
        : `${account.evidenceCount} supporting documents`,
    )
  }
  return parts.length > 0 ? parts.join(' · ') : 'Awaiting evidence'
}

function accountCoverageDetail(
  account: HouseholdAccountSummary,
  topGap: HouseholdAccountSummary['gapFlags'][number] | null,
) {
  const pricedPositionCount = account.pricedPositionCount ?? 0
  const parts = [
    topGap ? `${topGap.title}: ${topGap.detail}` : null,
    `Balance ${account.balanceFreshnessLabel.toLowerCase()}`,
    account.moneyRole === 'spend_driver'
      ? `Transactions ${account.transactionFreshnessLabel.toLowerCase()}`
      : 'Transactions not required',
    pricedPositionCount > 0
      ? `${(account.quoteFreshnessLabel ?? 'live quotes').toLowerCase()} across ${pricedPositionCount} priced position${pricedPositionCount === 1 ? '' : 's'}`
      : null,
    account.lastEvidenceAt
      ? `Last evidence ${formatRelativeTime(account.lastEvidenceAt)}`
      : 'No evidence linked yet',
    `${account.evidenceCount} source${account.evidenceCount === 1 ? '' : 's'}`,
  ].filter(Boolean)

  return parts.join(' · ')
}

function seedFromAccount(
  account: HouseholdAccountSummary,
): HouseholdTrackedAccountInput {
  return {
    label: account.label,
    assetGroup: account.assetGroup,
    accountType: account.accountType,
    sourceType: account.sourceType,
    matchKey:
      account.matchKey ??
      (account.accountOrigin !== 'tracked' ? account.id : ''),
    institutionName: account.institutionName ?? '',
    ownerName: account.ownerName ?? '',
    accountMask: account.accountMask ?? '',
    notes: account.notes ?? '',
  }
}

function moneyRoleLabel(role: string) {
  return role === 'spend_driver' ? 'Spending account' : 'Net worth only'
}

function accountEvidenceDate(
  value: string | null | undefined,
  daysSince: number | null | undefined,
) {
  if (!value) {
    return 'missing'
  }
  const ageLabel = daysSince == null ? null : `${daysSince}d old`
  return `${formatDate(value)}${ageLabel ? ` (${ageLabel})` : ''}`
}

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
          (account) =>
            account.gapFlags.length > 0 || account.freshnessStatus !== 'fresh',
        )?.id
      : undefined)
  const [openAccountId, setOpenAccountId] = useState<string | undefined>(
    focusedAccountId,
  )
  const deleteAccount = useDeleteHouseholdTrackedAccount()
  const documentsById = Object.fromEntries(
    documents.map((document) => [document.id, document]),
  )

  useEffect(() => {
    if (focusedAccountId) {
      setOpenAccountId(focusedAccountId)
    }
  }, [focusedAccountId])

  useEffect(() => {
    if (!selectedAccountId || openAccountId !== selectedAccountId) {
      return
    }
    const targetId =
      intent === 'evidence'
        ? `account-evidence-upload-${selectedAccountId}`
        : `account-${selectedAccountId}`
    const scrollTarget = document.getElementById(targetId)
    if (!scrollTarget) {
      return
    }
    requestAnimationFrame(() => {
      scrollTarget.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
    })
  }, [intent, openAccountId, selectedAccountId])

  const handleDelete = async (account: HouseholdAccountSummary) => {
    if (!account.trackedAccountId) return
    await deleteAccount.mutateAsync(account.trackedAccountId)
    setDeletingAccount(null)
  }

  return (
    <div className="space-y-4">
      {discoveredAccounts.length > 0 ? (
        <div
          className={`rounded-3xl border bg-surface-muted/15 p-5 ${
            focus === 'discovered'
              ? 'border-primary/50 ring-1 ring-primary/30'
              : 'border-border/40'
          }`}
        >
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-semibold text-text">
                Possible accounts Jenny found
              </p>
              <p className="mt-1 text-sm text-text-muted">
                Soft-added from statements and transfers. Confirm only real
                accounts you want included in money tracking.
              </p>
            </div>
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              {discoveredAccounts.length} possible account
              {discoveredAccounts.length === 1 ? '' : 's'}
            </p>
          </div>

          <div className="mt-4 grid gap-3 xl:grid-cols-2">
            {discoveredAccounts.map((account) => (
              <div
                key={account.key}
                className="rounded-2xl border border-border/40 bg-surface/70 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">
                      {account.suggestedLabel}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {[
                        account.assetGroup,
                        account.accountType,
                        account.institution,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                  </div>
                  <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1 text-xs text-text-muted">
                    {Math.round(account.confidence * 100)}% match
                  </span>
                </div>
                <p className="mt-3 text-sm text-text-muted">{account.detail}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-text-muted">
                  <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1">
                    Seen {account.occurrenceCount} time
                    {account.occurrenceCount === 1 ? '' : 's'}
                  </span>
                  {account.partialAccount ? (
                    <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1">
                      …{account.partialAccount}
                    </span>
                  ) : null}
                </div>
                <div className="mt-4">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setEditingAccount(null)
                      setDraftSeed({
                        label: account.suggestedLabel,
                        assetGroup: account.assetGroup,
                        accountType: account.accountType,
                        sourceType: account.sourceType,
                        institutionName: account.institution,
                        accountMask: account.partialAccount ?? '',
                        notes: account.sampleDescription ?? '',
                      })
                      setDialogOpen(true)
                    }}
                  >
                    <PlusCircle className="mr-2 h-4 w-4" />
                    Create tracked row
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="flex flex-col gap-3 rounded-3xl border border-border/40 bg-surface-muted/15 p-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold text-text">Accounts</p>
          <p className="mt-1 text-sm text-text-muted">
            Expand a row for uploads, linked documents, and account details.
          </p>
        </div>
        <Button
          type="button"
          onClick={() => {
            setEditingAccount(null)
            setDraftSeed(null)
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
          <Accordion
            type="single"
            collapsible
            className="w-full"
            value={openAccountId}
            onValueChange={setOpenAccountId}
          >
            {accounts.map((account) => {
              const topGap = account.gapFlags[0] ?? null
              const isFocused = account.id === focusedAccountId
              const pricedPositionCount = account.pricedPositionCount ?? 0
              return (
                <AccordionItem
                  key={account.id}
                  value={account.id}
                  id={`account-${account.id}`}
                  className={`px-5 ${
                    isFocused
                      ? 'border-primary/50 bg-primary/5 ring-1 ring-primary/30'
                      : ''
                  }`}
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
                        {pricedPositionCount > 0 ? (
                          <InfoBadge
                            label={account.quoteFreshnessLabel ?? 'Live quotes'}
                            detail={[
                              `${pricedPositionCount} priced position${pricedPositionCount === 1 ? '' : 's'}`,
                              account.quoteUpdatedAt
                                ? `oldest quote ${formatRelativeTime(account.quoteUpdatedAt)}`
                                : null,
                              account.quoteSource
                                ? `source ${account.quoteSource}`
                                : null,
                            ]
                              .filter(Boolean)
                              .join(' · ')}
                            variant={
                              account.quoteFreshnessStatus === 'fresh'
                                ? 'success'
                                : account.quoteFreshnessStatus === 'aging'
                                  ? 'warning'
                                  : account.quoteFreshnessStatus === 'stale'
                                    ? 'secondary'
                                    : 'outline'
                            }
                            className="bg-surface/70 text-text-muted"
                            interactive={false}
                          />
                        ) : null}
                        <InfoBadge
                          label="Coverage"
                          detail={accountCoverageDetail(account, topGap)}
                          variant="outline"
                          className="bg-surface/70 text-text-muted"
                          interactive={false}
                        />
                      </div>

                      <div className="text-left md:text-right">
                        <p className="text-lg font-semibold tabular-nums text-text">
                          {account.currentValue != null
                            ? formatCurrencyWhole(account.currentValue)
                            : '—'}
                        </p>
                        <p className="mt-1 text-xs text-text-muted">
                          {account.moneyRole === 'spend_driver'
                            ? 'Spending account'
                            : 'Net worth account'}
                        </p>
                      </div>
                    </div>
                  </AccordionTrigger>

                  <AccordionContent className="pb-5">
                    <div className="grid gap-4 xl:grid-cols-[0.92fr_1.08fr]">
                      <div className="space-y-4">
                        <div className="flex flex-wrap items-center justify-end gap-2">
                          {account.trackedAccountId ? (
                            <>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setEditingAccount(account)
                                  setDraftSeed(null)
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
                            </>
                          ) : (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingAccount(null)
                                setDraftSeed(seedFromAccount(account))
                                setDialogOpen(true)
                              }}
                            >
                              <Pencil className="mr-2 h-4 w-4" />
                              Track / rename
                            </Button>
                          )}
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                              Status
                            </p>
                            <div className="mt-2 space-y-1 text-sm text-text">
                              <p>
                                Balance {account.balanceFreshnessLabel} ·{' '}
                                {accountEvidenceDate(
                                  account.lastBalanceAt,
                                  account.daysSinceBalance,
                                )}
                              </p>
                              <p>
                                {account.moneyRole === 'spend_driver'
                                  ? `Transactions ${account.transactionFreshnessLabel} · ${accountEvidenceDate(
                                      account.lastTransactionAt,
                                      account.daysSinceTransaction,
                                    )}`
                                  : 'Transactions not required'}
                              </p>
                              {pricedPositionCount > 0 ? (
                                <p>
                                  Quotes {account.quoteFreshnessLabel ?? 'Live'}
                                </p>
                              ) : null}
                              <p className="text-text-muted">
                                {account.lastEvidenceAt
                                  ? `Last evidence ${formatRelativeTime(account.lastEvidenceAt)}`
                                  : 'No evidence linked yet'}
                              </p>
                              <p className="text-text-muted">
                                {account.evidenceCount} source
                                {account.evidenceCount === 1 ? '' : 's'}
                              </p>
                            </div>
                          </div>
                          <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                              Identity
                            </p>
                            <div className="mt-2 space-y-1 text-sm text-text">
                              <p>{moneyRoleLabel(account.moneyRole)}</p>
                              <p className="text-text-muted">
                                {account.accountOrigin === 'tracked'
                                  ? 'Tracked account'
                                  : account.accountOrigin === 'portfolio'
                                    ? 'Portfolio account'
                                    : account.matchStatus === 'candidate'
                                      ? 'Candidate account'
                                      : 'Evidence-backed'}
                              </p>
                            </div>
                          </div>
                        </div>

                        <div
                          id={`account-evidence-upload-${account.id}`}
                          className="scroll-mt-40"
                        >
                          <EvidenceUploadComposer
                            compact
                            highlighted={
                              account.id === selectedAccountId &&
                              intent === 'evidence'
                            }
                            title="Add evidence to this account"
                            description="Use this when you already know the account. Jenny still verifies the contents before applying any update."
                            accountId={account.id}
                            accountLabel={account.label}
                          />
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div className="rounded-2xl border border-border/30 bg-surface-muted/20 p-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                              Supporting documents
                            </p>
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
                                        ? formatRelativeTime(
                                            document.uploadedAt,
                                          )
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
