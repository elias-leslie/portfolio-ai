'use client'

import { useEffect, useState } from 'react'
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
  HouseholdTrackedAccountInput,
} from '@/lib/api/household'
import {
  useCreateHouseholdTrackedAccount,
  useUpdateHouseholdTrackedAccount,
} from '@/lib/hooks/useHousehold'

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
      { value: 'roth_401k', label: 'Roth 401(k)' },
      { value: '403b', label: '403(b)' },
      { value: 'roth_403b', label: 'Roth 403(b)' },
      { value: '457b', label: '457(b)' },
      { value: 'governmental_457b', label: 'Governmental 457(b)' },
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

function defaultAccountType(assetGroup: string) {
  return ACCOUNT_TYPE_OPTIONS[assetGroup]?.[0]?.value ?? 'other'
}

function identityManagedByCanonicalAccount(
  account?: HouseholdAccountSummary | null,
): boolean {
  if (!account) return false
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
    householdAccountId:
      account?.householdAccountId ?? seed?.householdAccountId ?? null,
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

export interface TrackedAccountDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  account?: HouseholdAccountSummary | null
  seed?: HouseholdTrackedAccountInput | null
}

export function TrackedAccountDialog({
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
    if (open) setForm(buildInitialState(account, seed))
  }, [account, open, seed])

  const accountTypeOptions =
    ACCOUNT_TYPE_OPTIONS[form.assetGroup] ?? ACCOUNT_TYPE_OPTIONS.other
  const canSubmit = form.label.trim().length > 0
  const isEditing = Boolean(
    account?.trackedAccountId || account?.householdAccountId,
  )
  const isPrefilled = Boolean(seed) && !isEditing
  const identityLocked = Boolean(
    account && identityManagedByCanonicalAccount(account),
  )
  const showIdentityFields = !identityLocked
  const showCanonicalTypeOverride =
    identityLocked && form.assetGroup === 'retirement'

  const dialogTitle = isEditing
    ? 'Edit account'
    : isPrefilled
      ? 'Confirm account'
      : 'Add account'
  const dialogDescription = isPrefilled
    ? 'Jenny found this account from evidence. Confirm the details once, then keep attaching evidence to this row over time.'
    : identityLocked
      ? 'Update the account display details.'
      : 'Create a real account row first, then let Jenny attach evidence to it over time.'
  const submitLabel =
    isEditing || isPrefilled ? 'Save account details' : 'Create account'

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
      await createAccount.mutateAsync({
        ...form,
        householdAccountId:
          account?.householdAccountId ?? form.householdAccountId,
      })
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

          {showIdentityFields ? (
            <>
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
            </>
          ) : null}

          {showCanonicalTypeOverride ? (
            <div className="grid gap-2">
              <Label htmlFor="money-account-type-override">
                Retirement account type
              </Label>
              <Select
                value={form.accountType}
                onValueChange={(accountType) =>
                  setForm((current) => ({ ...current, accountType }))
                }
              >
                <SelectTrigger id="money-account-type-override">
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
              <p className="text-xs text-muted-foreground">
                Use this when imported evidence identifies the account family
                but misses tax treatment, such as Roth vs pre-tax 403(b).
              </p>
            </div>
          ) : null}

          <div className="grid gap-2">
            <Label htmlFor="money-account-owner">Owner</Label>
            <Input
              id="money-account-owner"
              value={form.ownerName ?? ''}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  ownerName: event.target.value,
                }))
              }
              placeholder="Alex Demo"
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
